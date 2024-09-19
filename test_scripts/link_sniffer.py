import rp2
import utime
from ulab import numpy as np

from machine import Pin
from micropython import const

# -----------------------------------------------
# add type hints for the rp2.PIO Instructions
from typing_extensions import TYPE_CHECKING # type: ignore
if TYPE_CHECKING:
    from rp2.asm_pio import *
# -----------------------------------------------


def timeit(f, *args, **kwargs):
    func_name = str(f).split(' ')[1]
    def new_func(*args, **kwargs):
        t = utime.ticks_us()
        result = f(*args, **kwargs)
        micros = utime.ticks_diff(utime.ticks_us(), t)
        print(f'{__name__} {func_name} execution time: {micros} us')
        return result
    return new_func

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
)
def gb_link(): 
    wrap_target() 
    set(x, 6)             # set loop to run 6 + 1 times
    wait(0, gpio, 5)[2]      # wait for falling edge
    wait(1, gpio, 5)[2]   # wait for rising edge
    label("bitloop")      
    in_(pins, 1)          # input bit from GB to ISR
    wait(0, gpio, 5)[2]   # wait for falling edge
    wait(1, gpio, 5)[1]   # wait for rising edge
    jmp(x_dec, "bitloop") # loop through the rest of the bits
    in_(pins, 1)          # input last bit from GB
    push(noblock)         # push the received value from ISR to RX FIFO
    irq(rel(0))           # set interrupt
    wrap()

@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
)
def printer_link(): 
    wrap_target() 
    set(x, 6)             # set loop to run 6 + 1 times
    wait(0, gpio, 5)[2]      # wait for falling edge
    wait(1, gpio, 5)[2]   # wait for rising edge
    label("bitloop")      
    in_(pins, 1)          # input bit from GB to ISR
    wait(0, gpio, 5)[2]   # wait for falling edge
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
    @timeit
    def __init__(self):
        self.bytes_received = 0
        # CLOCK PIN 5, ENTERED MANUALLY IN PROGRAM ABOVE
        self.gb_pio = rp2.StateMachine(
            0, gb_link, 
            in_base=Pin(2),
            freq = int(1e6)
        )
        self.printer_pio = rp2.StateMachine(
            1, printer_link, 
            in_base=Pin(3),
            freq = int(1e6)
        )
        self.packet_state = STATE_IDLE
        self.remaining_bytes = 0
        self.packet = GBPacket()
        self.gb_byte = 0
        self.printer_status = 0
        self.complete_packet = False
        self.last_packet_time = utime.ticks_us()
        self.care_about_next_byte = False
    
    def startup(self):
        self.gb_pio.irq(self.gb_interrupt)
        self.printer_pio.irq(self.printer_interrupt)
        self.gb_pio.active(1)
        self.printer_pio.active(1)
        print('ready!')
        self.run()
        self.gb_pio.active(0)
    
    def run(self):
        while True:
            self.packet_wait_start = utime.ticks_us()
            while not self.complete_packet:
                pass
            self.handle_packet()
            self.complete_packet = False

    def printer_interrupt(self, mach):
        self.printer_byte = mach.get()
        if self.care_about_next_byte:
            self.printer_status = self.printer_byte
            self.care_about_next_byte = False
        elif self.printer_byte == 0x81:
            self.care_about_next_byte = True
        else:
            return
        # print(f'IRQ Received byte {self.printer_byte:02x}')

    def gb_interrupt(self, mach):
        self.gb_byte = mach.get()
        
        if self.packet_state == STATE_IDLE:
            if self.gb_byte == 0x88:
                self.packet_state = STATE_MAGICBYTES_PARTIAL
                self.packet_start = utime.ticks_us()
            else:
                print('Bad first magic byte!')

        elif self.packet_state == STATE_MAGICBYTES_PARTIAL:
            if self.gb_byte == 0x33:
                self.packet_state = STATE_HEADER
                self.remaining_bytes = 4
            else:
                self.packet_state = STATE_IDLE
                print('bad second magic byte!')

        elif self.packet_state == STATE_HEADER:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 3:
                self.packet.command = self.gb_byte
                # self.packet.calc_checksum += self.gb_byte
            elif self.remaining_bytes == 2:
                self.packet.compression_flag = self.gb_byte
                # self.packet.calc_checksum += self.gb_byte
            elif self.remaining_bytes == 1:
                self.packet.data_length = self.gb_byte
                # self.packet.calc_checksum += self.gb_byte
            else:
                self.packet.data_length += self.gb_byte * 256
                # self.packet.calc_checksum += self.gb_byte
                if self.packet.data_length:
                    self.packet_state = STATE_PAYLOAD
                    self.remaining_bytes = self.packet.data_length
                else:
                    self.packet_state = STATE_CHECKSUM
                    self.remaining_bytes = 2
        
        elif self.packet_state == STATE_PAYLOAD:
            idx = self.packet.data_length - self.remaining_bytes
            self.remaining_bytes -= 1
            self.packet.data[idx] = self.gb_byte
            if self.remaining_bytes == 0:
                self.packet_state = STATE_CHECKSUM
                self.remaining_bytes = 2
        
        elif self.packet_state == STATE_CHECKSUM:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 1:
                self.packet.checksum = self.gb_byte
            else:
                self.packet.checksum += self.gb_byte * 256
                self.packet_state = STATE_RESPONSE_READY
        
        elif self.packet_state == STATE_RESPONSE_READY:
            self.packet_state = STATE_RESPONSE_PARTIAL

        elif self.packet_state == STATE_RESPONSE_PARTIAL:
            self.packet_state = STATE_IDLE
            self.complete_packet = True            

    def handle_packet(self):
        packet_time = (utime.ticks_us() - self.last_packet_time)
        print(
            f'Packet type: {self.packet.command:1x}, '
            f'Printer status: {self.printer_status:02x}, '
            f'Send time: {packet_time} us, '
        )
        self.last_packet_time = utime.ticks_us()

link = GBLink()
link.startup()


