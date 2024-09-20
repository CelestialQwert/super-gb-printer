import rp2
import utime

from machine import Pin
from micropython import const
from ulab import numpy as np

# -----------------------------------------------
# add type hints for the rp2.PIO Instructions
from typing_extensions import TYPE_CHECKING # type: ignore
if TYPE_CHECKING:
    from rp2.asm_pio import *
# -----------------------------------------------

import data_buffer
import fake_lcd
import timeit
import pinout as pin

STATE_IDLE = const(0)
STATE_MAGICBYTES_PARTIAL = const(1)
STATE_HEADER = const(2)
STATE_PAYLOAD = const(3)
STATE_CHECKSUM = const(4)
STATE_RESPONSE_READY = const(5)
STATE_RESPONSE_PARTIAL = const(6)
STATE_TIMEOUT = const(7)

COMMAND_INIT = const(1)
COMMAND_PRINT = const(2)
COMMAND_DATA = const(4)
COMMAND_BREAK = const(8)
COMMAND_STATUS = const(0xF)


@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    set_init=rp2.PIO.OUT_LOW,
    out_init=rp2.PIO.OUT_LOW,
)
def gb_link_pio():
    set(x, 6)             # set loop to run 6 + 1 times
    wait(0, gpio, 2)      # wait for falling edge
    set(pins, 1)          # byte started, turn on LED
    pull(noblock)         # pull value from TX FIFO to OSR
    out(null, 24)         # shift left by 24, keeping 8 bits of desired data
    out(pins, 1)          # out the MSB bit in OSR to GB
    wait(1, gpio, 2)[2]   # wait for rising edge
    label("loop")      
    in_(pins, 1)          # MSB input bit from GB to ISR
    wait(0, gpio, 2)[2]   # wait for falling edge
    out(pins, 1)          # output the next bit from OSR to GB
    wait(1, gpio, 2)[1]   # wait for rising edge
    jmp(x_dec, "loop")    # loop through the rest of the bits
    in_(pins, 1)          # input last bit from GB
    push(noblock)         # push the received value from ISR to RX FIFO
    irq(rel(0))           # set interrupt
    set(pins, 0)          # byte complete, turn off LED

class GBLink:
    def __init__(self, buffer=None, lcd=None):

        self.data_buffer = buffer if buffer else data_buffer.DataBuffer()
        self.lcd = lcd if lcd else fake_lcd.FakeLCD()
        self.pio_mach = rp2.StateMachine(
            0, gb_link_pio, 
            in_base=Pin(pin.GB_IN),
            out_base=Pin(pin.GB_OUT),
            set_base=Pin(pin.GB_LED_ACTIVITY),
            freq = int(1e6)
        )
        self.pio_enabled_led = Pin(pin.GB_PIO_ENABLED, Pin.OUT)
        self.packet_state = STATE_IDLE
        self.remaining_bytes = 0
        self.packet = data_buffer.GBPacket()
        self.byte_received = False
        self.complete_packet = False
        self.rx_byte = 0
        self.tx_byte = 0
        self.printer_status = 0
        self.end_of_print_data = False
        self.last_packet_time = utime.ticks_ms()
        self.fake_print_ticks = 0

    def startup(self):
        self.pio_mach.irq(self.gb_interrupt)
        self.shutdown_pio_mach()
        self.startup_pio_mach()
        print('gb link ready!')
    
    def shutdown_pio_mach(self):
        print('Shutting down PIO')
        self.pio_mach.active(0)
        self.pio_enabled_led.off()
        while self.pio_mach.rx_fifo():
            print('Draining RX FIFO')
            _ = self.pio_mach.get()
        while self.pio_mach.tx_fifo():
            print('Draining TX FIFO')
            self.pio_mach.exec('pull(noblock)')
            self.pio_mach.exec('out(null, 32)')

    def startup_pio_mach(self):
        print('Starting PIO')
        self.pio_mach.restart()
        self.pio_enabled_led.on()
        self.pio_mach.active(1)
        self.pio_mach.put(0)
    
    def check_timeout(self):   
        this_time = utime.ticks_ms()
        if utime.ticks_diff(this_time, self.last_packet_time) > 3000:
            print(f'Printer timeout at {this_time}')
            self.shutdown_pio_mach()
            self.packet_state = STATE_IDLE
            self.printer_status = 0
            self.data_buffer.clear_packets()
            self.lcd.clear()
            self.lcd.print("Ready")
            self.startup_pio_mach()
            self.last_packet_time = utime.ticks_ms()
    
    def check_print_ready(self):
        this_time = utime.ticks_ms()
        if (
            utime.ticks_diff(this_time, self.last_packet_time) > 1000
            and self.end_of_print_data
        ):
            self.end_of_print_data = False
            return True
        return False

    def gb_interrupt(self, pio_mach):

        if self.pio_mach.rx_fifo():
            self.rx_byte = self.pio_mach.get() # & 0xFF
        else:
            print('no RX FIFO byte!')
            self.rx_ryte = 0
        # print(f'IRQ Received byte {self.rx_byte:02x}')
        # print(f'Had sent {self.tx_byte:02x}')

        self.tx_byte = 0x00

        if self.packet_state == STATE_IDLE:
            if self.rx_byte == 0x88:
                self.packet_state = STATE_MAGICBYTES_PARTIAL
                self.packet_start = utime.ticks_us()
            else:
                print('First magic byte bad!')
                self.tx_byte = 0x40

        elif self.packet_state == STATE_MAGICBYTES_PARTIAL:
            if self.rx_byte == 0x33:
                self.packet_state = STATE_HEADER
                self.remaining_bytes = 4
            else:
                print('Second magic byte bad!')
                self.tx_byte = 0x40
                self.packet_state = STATE_IDLE

        elif self.packet_state == STATE_HEADER:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 3:
                self.packet.command = self.rx_byte
                # self.packet.calc_checksum += self.rx_byte
            elif self.remaining_bytes == 2:
                self.packet.compression_flag = self.rx_byte
                # self.packet.calc_checksum += self.rx_byte
            elif self.remaining_bytes == 1:
                self.packet.data_length = self.rx_byte
                # self.packet.calc_checksum += self.rx_byte
            else:
                self.packet.data_length += self.rx_byte * 256
                # self.packet.calc_checksum += self.rx_byte
                if self.packet.data_length:
                    self.packet_state = STATE_PAYLOAD
                    self.remaining_bytes = self.packet.data_length
                else:
                    self.packet_state = STATE_CHECKSUM
                    self.remaining_bytes = 2
        
        elif self.packet_state == STATE_PAYLOAD:
            idx = self.packet.data_length - self.remaining_bytes
            self.remaining_bytes -= 1
            self.packet.data[idx] = self.rx_byte
            if self.remaining_bytes == 0:
                self.packet_state = STATE_CHECKSUM
                self.remaining_bytes = 2
        
        elif self.packet_state == STATE_CHECKSUM:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 1:
                self.packet.checksum = self.rx_byte
                self.tx_byte = 0x81 # first response byte
            else:
                self.packet.checksum += self.rx_byte * 256
                self.packet_state = STATE_RESPONSE_READY
                self.tx_byte = self.printer_status #0x81 # first response byte
        
        elif self.packet_state == STATE_RESPONSE_READY:
            self.packet_state = STATE_RESPONSE_PARTIAL
            self.tx_byte = self.printer_status

        elif self.packet_state == STATE_RESPONSE_PARTIAL:
            self.packet_state = STATE_IDLE
            self.complete_packet = True

            self.packet_end = utime.ticks_us()                

        self.pio_mach.put(self.tx_byte)
    
    def check_handle_packet(self):
        if not self.complete_packet:
            return
        
        print(
            f'Packet type: {self.packet.command}, '
            f'Printer status: {self.printer_status}, '
            f'Print ticks: {self.fake_print_ticks}, ' 
            # f'Packet time: {utime.ticks_ms()}'
        )

        if self.packet.command == COMMAND_INIT:
            self.printer_status = 0x00
        elif self.packet.command == COMMAND_DATA:
            if self.packet.data_length == 0:
                print('Received stop data packet')
            else:
                self.data_buffer.dma_copy_new_packet(self.packet)
                pck = self.data_buffer.num_packets
                cmp = bool(self.packet.compression_flag)
                self.data_buffer.gb_compression_flag[pck] = cmp
                self.printer_status = 0x08
                if self.data_buffer.num_packets == 1:
                    self.lcd.clear()
                    self.lcd.print("Packet 1")
                else:
                    self.lcd.set_cursor(7, 0)
                    self.lcd.print(str(self.data_buffer.num_packets))
        elif self.packet.command == COMMAND_PRINT:
            self.printer_status = 0x06
            if (self.packet.data[1] % 16) == 0:
                print('This is not the end of a print!')
                self.end_of_print_data = False
            else:
                print('Will be end of print!')
                self.end_of_print_data = True
            self.fake_print_ticks = 5
            # self.lcd.clear()
            # self.lcd.print("Printing")
        elif self.packet.command == COMMAND_BREAK:
            self.printer_status = 0x00
        elif self.packet.command == COMMAND_STATUS:
            if self.printer_status == 0x06:
                self.fake_print_ticks -= 1
                if self.fake_print_ticks == 0:
                    self.printer_status = 0x04
            elif self.printer_status == 0x04:
                self.printer_status = 0x00
                    
        self.complete_packet = False
        self.last_packet_time = utime.ticks_ms()

if __name__ == "__main__":
    gb_link = GBLink()