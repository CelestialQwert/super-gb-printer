import rp2
import utime

from machine import Pin
from micropython import const


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
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    set_init=rp2.PIO.OUT_HIGH,
    out_init=rp2.PIO.OUT_LOW,
    sideset_init=rp2.PIO.OUT_LOW
)
def gb_link(): 
    wrap_target() 
    set(x, 6)             # set loop to run 6 + 1 times
    pull(noblock)         # pull value from TX FIFO to OSR
    wait(0, gpio, 5)      # wait for falling edge
    set(pins, 0)          # turn off LED
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
    @timeit
    def __init__(self):
        # CLOCK PIN 5, ENTERED MANUALLY IN PROGRAM ABOVE
        self.sm = rp2.StateMachine(
            0, gb_link, 
            in_base=Pin(2),
            out_base=Pin(3),
            set_base=Pin(25),
            sideset_base=Pin(25),
            freq = int(1e6)
        )
        self.packet_state = STATE_IDLE
        self.remaining_bytes = 0
        self.packet = GBPacket()
        self.complete_packet = False
        self.pages_received = 0
        self.rx_byte = 0
        self.tx_byte = 0
        self.printer_status = 0
        self.fake_print_ticks = 0
        self.bytes_received = 0
        self.last_byte_received = 0
    
    def startup(self):
        self.sm.irq(self.gb_interrupt)
        self.sm.restart()
        while self.sm.rx_fifo():
            print('Draining RX FIFO')
            _ = self.sm.get()
        while self.sm.tx_fifo():
            print('Draining TX FIFO')
            self.sm.exec('pull(noblock)')
            self.sm.exec('out(null, 32)')
        self.sm.active(1)
        # self.sm.put(0)
        print('ready!')
        self.run()
        self.sm.active(0)
    
    def run(self):
        while True:
            while not self.complete_packet:
                pass
            self.handle_packet()
            self.complete_packet = False

    def old_gb_interrupt(self, mach):
        bite = mach.get()
        self.bytes_received += 1
        if self.bytes_received % 2:
            mach.put(0x81)
        else:
            mach.put(0x81)
        next_byte = utime.ticks_us()
        print(
            f'Received byte {bite:02x}, '
            f'time {next_byte - self.last_byte_received} us'
        )
        self.last_byte_received = next_byte

    def gb_interrupt(self, mach):
        self.rx_byte = mach.get() # & 0xFF
        # print(f'IRQ Received byte {self.rx_byte:02x}')
        # print(f'Had sent {self.tx_byte:02x}')

        self.tx_byte = 0x81

        if self.packet_state == STATE_IDLE:
            if self.rx_byte == 0x88:
                self.packet_state = STATE_MAGICBYTES_PARTIAL
                self.packet_start = utime.ticks_us()
            else:
                print('First magic byte bad!')

        elif self.packet_state == STATE_MAGICBYTES_PARTIAL:
            if self.rx_byte == 0x33:
                self.packet_state = STATE_HEADER
                self.remaining_bytes = 4
            else:
                self.packet_state = STATE_IDLE
                print('#2 magic byte bad!')

        elif self.packet_state == STATE_HEADER:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 3:
                self.packet.command = self.rx_byte
            elif self.remaining_bytes == 2:
                self.packet.compression_flag = self.rx_byte
            elif self.remaining_bytes == 1:
                self.packet.data_length = self.rx_byte
            else:
                self.packet.data_length += self.rx_byte * 256
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
                self.tx_byte = self.printer_status# 0x81 # first response byte
        
        elif self.packet_state == STATE_RESPONSE_READY:
            self.packet_state = STATE_RESPONSE_PARTIAL
            self.tx_byte = self.printer_status

        elif self.packet_state == STATE_RESPONSE_PARTIAL:
            self.packet_state = STATE_IDLE
            self.complete_packet = True
            # print('packet done')
            self.packet_end = utime.ticks_us()                

        self.sm.put(self.tx_byte)

    def handle_packet(self):
        print(
            f'Packet type: {self.packet.command}, '
            f'Printer status: {self.printer_status}, '
            f'Print ticks: {self.fake_print_ticks}' 
        )

        if self.packet.command == COMMAND_INIT:
            self.printer_status = 0x00
            self.pages_received = 0
        elif self.packet.command == COMMAND_DATA:
            if self.packet.data_length == 0:
                print('Received stop data packet')
            else:
                self.pages_received += 1
                self.printer_status = 0x08
        elif self.packet.command == COMMAND_PRINT:
            self.printer_status = 0x06
            self.fake_print_ticks = 10
        elif self.packet.command == COMMAND_BREAK:
            self.printer_status = 0x00
            self.pages_received = 0
        elif self.packet.command == COMMAND_STATUS:
            if self.printer_status == 0x06:
                self.fake_print_ticks -= 1
                if self.fake_print_ticks == 0:
                    self.printer_status = 0x04
            elif self.printer_status == 0x04:
                self.printer_status = 0x00


link = GBLink()
link.startup()


