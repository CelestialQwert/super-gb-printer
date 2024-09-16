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
    set_init=rp2.PIO.OUT_HIGH,
    out_init=rp2.PIO.OUT_LOW,
    sideset_init=rp2.PIO.OUT_LOW
)
def gb_link_pio(): 
    wrap_target() 
    set(x, 6)             # set loop to run 6 + 1 times
    wait(0, gpio, 5)      # wait for falling edge
    set(pins, 0)          # turn off LED
    pull(noblock)         # pull value from TX FIFO to OSR
    out(null, 24)         # shift left by 24
    out(pins, 1)          # out the MSB bit in OSR to GB
    wait(1, gpio, 5)[2]   # wait for rising edge
    label("bitloop")      
    in_(pins, 1)          # input bit from GB to ISR
    wait(0, gpio, 5)[2]   # wait for falling edge
    out(pins, 1)          # output bit from OSR to GB
    wait(1, gpio, 5)[1]   # wait for rising edge
    jmp(x_dec, "bitloop") # loop through the rest of the bits
    in_(pins, 1)          # input last bit from GB
    push(noblock)         # push the received value from ISR to RX FIFO
    irq(rel(0))           # set interrupt
    wrap()


class GBPacket():
    def __init__(self):
        self.command = 0
        self.compression_flag = 0
        self.data_length = 0
        self.data = bytearray(0x280)
        self.checksum = 0
        self.calc_checksum = 0


class GBLink:
    def __init__(self, buffer=None, lcd=None):

        self.data_buffer = buffer if buffer else data_buffer.DataBuffer()

        self.lcd = lcd if lcd else fake_lcd.FakeLCD()

        self.pio_mach = rp2.StateMachine(
            0, gb_link_pio, 
            in_base=Pin(2),
            out_base=Pin(3),
            set_base=Pin(25),
            sideset_base=Pin(25),
            freq = int(1e6)
        )

        self.packet_state = STATE_IDLE
        self.remaining_bytes = 0
        self.packet = GBPacket()
        self.byte_received = False
        self.complete_packet = False
        self.rx_byte = 0
        self.tx_byte = 0
        self.printer_status = 0
        self.end_of_print = True

        # timing info
        self.packet_wait_start = 0
        self.packet_end = 0
        self.packet_start = 0
        self.fake_print_ticks = 0

    def startup(self):
        self.pio_mach.irq(self.gb_interrupt)
        self.restart_pio_mach()
        print('gb link ready!')
        # self.run()
        # self.pio_mach.active(0)

    def restart_pio_mach(self):
        self.pio_mach.active(0)
        print('Restarting PIO')
        self.pio_mach.restart()
        while self.pio_mach.rx_fifo():
            print('Draining RX FIFO')
            _ = self.pio_mach.get()
        while self.pio_mach.tx_fifo():
            print('Draining TX FIFO')
            self.pio_mach.exec('pull(noblock)')
            self.pio_mach.exec('out(null, 32)')
        self.lcd.clear()
        self.lcd.print("Ready")
        self.pio_mach.active(1)
    
    def run(self):
        while True:
            self.packet_wait_start = utime.ticks_us()
            self.last_packet_time = utime.ticks_ms()
            while True:
                if self.complete_packet:
                    self.handle_packet()
                    self.complete_packet = False
                    self.last_packet_time = utime.ticks_ms()
                this_time = utime.ticks_ms()
                if utime.ticks_diff(this_time, self.last_packet_time) > 3000:
                    print(f'Printer timeout at {this_time}')
                    self.packet_state = STATE_IDLE
                    self.printer_status = 0
                    self.data_buffer.clear_packets()
                    self.restart_pio_mach()
                    self.last_packet_time = utime.ticks_ms()

    
    def gb_interrupt(self, pio_mach):

        if self.pio_mach.rx_fifo():
            self.rx_byte = self.pio_mach.get() # & 0xFF
        else:
            print('no RX FIFO byte?')
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
            else:
                self.packet.checksum += self.rx_byte * 256
                self.packet_state = STATE_RESPONSE_READY
                self.tx_byte = 0x81 # first response byte
        
        elif self.packet_state == STATE_RESPONSE_READY:
            self.packet_state = STATE_RESPONSE_PARTIAL
            self.tx_byte = self.printer_status

        elif self.packet_state == STATE_RESPONSE_PARTIAL:
            self.packet_state = STATE_IDLE
            self.complete_packet = True

            self.packet_end = utime.ticks_us()                

        self.pio_mach.put(self.tx_byte)
    
    def handle_packet(self):
        # packet_time = (self.packet_end-self.packet_start)
        # packet_spacing = (self.packet_start-self.packet_wait_start)
        print(
            f'Packet type: {self.packet.command}, '
            # f'Send time: {packet_time} us, '
            # f'Time between packets: {packet_spacing} us, '
            f'Printer status: {self.printer_status}, '
            f'Print ticks: {self.fake_print_ticks}' 
        )

        if self.packet.command == COMMAND_INIT:
            self.printer_status = 0x00
        elif self.packet.command == COMMAND_DATA:
            if self.packet.data_length == 0:
                print('Received stop data packet')
            else:
                if self.data_buffer.num_packets == 0:
                    self.lcd.clear()
                    self.lcd.print("Receiving")
                self.data_buffer.dma_copy_new_packet(self.packet.data)
                self.printer_status = 0x08
        elif self.packet.command == COMMAND_PRINT:
            self.printer_status = 0x06
            if (self.packet.data[1] % 16) == 0:
                print('This is not the end of a print!')
                self.end_of_print = False
            else:
                print('Will be end of print!')
                self.end_of_print = True
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
                if self.end_of_print:
                    self.lcd.clear()
                    self.lcd.print(f"Done")
                    self.data_buffer.clear_packets()


if __name__ == "__main__":
    gb_link = GBLink()