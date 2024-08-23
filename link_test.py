import time
import rp2
import utime
from micropython import const
from machine import Pin
from ulab import numpy as np


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
def gb_link(): 
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
        # self.data = np.zeros(0x280, dtype=np.uint8)
        self.checksum = 0
        self.calc_checksum = 0

class GBLink:
    def __init__(self):
        self.bytes_received = 0
        # CLOCK PIN 5, ENTERED MANUALLY IN PROGRAM ABOVE
        self.sm = rp2.StateMachine(
            0, gb_link, 
            in_base=Pin(2),
            out_base=Pin(3),
            set_base=Pin(25),
            sideset_base=Pin(25),
            freq = int(1e6)
        )
        self.state = STATE_IDLE
        self.remaining_bytes = 0
        self.packets = [GBPacket() for _ in range(12)]
        self.packet_idx = 0
        self.current_packet = self.packets[self.packet_idx]
        self.got_packet = False
        self.data_buffer = np.zeros((9, 0x280), dtype=np.uint8)
        self.rx_byte = 0
        self.tx_byte = 0
        self.status = 0
        self.packet_wait_start = 0
        self.packet_end = 0
        self.packet_start = 0
        self.fake_print_ticks = 0
    
    def startup(self):
        self.sm.irq(self.gb_interrupt)
        self.sm.active(1)
        self.sm.put(0x00)
        self.run()
        self.sm.active(0)
    
    def run(self):
        while True:
            self.packet_wait_start = utime.ticks_us()
            while not self.got_packet:
                pass
            self.handle_packet()
            self.got_packet = False

    def old_gb_interrupt(self, mach):
        bite = mach.get()
        self.bytes_received += 1
        if self.bytes_received % 2:
            mach.put(0x40)
        else:
            mach.put(0x81)
        print(f'Received byte {bite:08x}')

    def gb_interrupt(self, mach):
        self.rx_byte = mach.get() # & 0xFF
        # print(f'IRQ Received byte {self.rx_byte:02x}')
        # print(f'Had sent {self.tx_byte:02x}')
        self.process_byte()
            
    def process_byte(self):
        self.tx_byte = 0x00

        if self.state == STATE_IDLE:
            self.tx_byte = 0x00
            if self.rx_byte == 0x88:
                self.state = STATE_MAGICBYTES_PARTIAL
                self.packet_start = utime.ticks_us()

        elif self.state == STATE_MAGICBYTES_PARTIAL:
            if self.rx_byte == 0x33:
                self.state = STATE_HEADER
                self.remaining_bytes = 4
            else:
                self.state = STATE_IDLE

        elif self.state == STATE_HEADER:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 3:
                self.current_packet.command = self.rx_byte
                # self.current_packet.calc_checksum += self.rx_byte
            elif self.remaining_bytes == 2:
                self.current_packet.compression_flag = self.rx_byte
                # self.current_packet.calc_checksum += self.rx_byte
            elif self.remaining_bytes == 1:
                self.current_packet.data_length = self.rx_byte
                # self.current_packet.calc_checksum += self.rx_byte
            else:
                self.current_packet.data_length += self.rx_byte * 256
                # self.current_packet.calc_checksum += self.rx_byte
                if self.current_packet.data_length:
                    self.state = STATE_PAYLOAD
                    self.remaining_bytes = self.current_packet.data_length
                else:
                    self.state = STATE_CHECKSUM
                    self.remaining_bytes = 2
        
        elif self.state == STATE_PAYLOAD:
            idx = self.current_packet.data_length - self.remaining_bytes
            self.remaining_bytes -= 1
            self.current_packet.data[idx] = self.rx_byte
            if self.remaining_bytes == 0:
                self.state = STATE_CHECKSUM
                self.remaining_bytes = 2
        
        elif self.state == STATE_CHECKSUM:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 1:
                self.current_packet.checksum = self.rx_byte
            else:
                self.current_packet.checksum += self.rx_byte * 256
                self.state = STATE_RESPONSE_READY
                self.tx_byte = 0x81 # first response byte
        
        elif self.state == STATE_RESPONSE_READY:
            self.state = STATE_RESPONSE_PARTIAL
            self.tx_byte = self.status

        elif self.state == STATE_RESPONSE_PARTIAL:
            self.state = STATE_IDLE
            self.got_packet = True
            self.packet_end = utime.ticks_us()
            packet_time = (self.packet_end-self.packet_start)
            packet_spacing = (self.packet_start-self.packet_wait_start)
            print(
                f'Packet type: {self.current_packet.command}, '
                f'Send time: {packet_time} us '
                f'Time since last packet: {packet_spacing} us',
                f'Print ticks: {self.fake_print_ticks}',
            )

        self.sm.put(self.tx_byte)

    def handle_packet(self):
        if self.current_packet.command == COMMAND_INIT:
            self.status = 0x00
            self.packet_idx  = 0
            self.current_packet = self.packets[self.packet_idx]
        elif self.current_packet.command == COMMAND_DATA:
            self.packet_idx += 1
            self.current_packet = self.packets[self.packet_idx]
        elif self.current_packet.command == COMMAND_PRINT:
            self.status = 0x06
            self.fake_print_ticks = 20
            self.copy_data()
        elif self.current_packet.command == COMMAND_BREAK:
            self.status = 0x00
            self.packet_idx = 0
        elif (
            self.current_packet.command == COMMAND_STATUS
            and self.status == 0x06
        ):
            self.fake_print_ticks -= 1
            if self.fake_print_ticks == 0:
                self.status = 0x00
                # self.packet_idx = 0
                self.current_packet = self.packets[self.packet_idx]
        
    def copy_data(self):
        for i in range(9):
            self.data_buffer[i,:] = self.packets[i].data
            print(f"Page {i} copied to buffer")



link = GBLink()
link.startup()


