import time
import rp2
from machine import Pin
from ulab import numpy as np


STATE_IDLE = 0
STATE_MAGICBYTES_PARTIAL = 1
STATE_HEADER = 2
STATE_PAYLOAD = 3
STATE_DATASUM = 4
STATE_DATASUM_DONE = 5
STATE_RESPONSE_PARTIAL = 6
STATE_TIMEOUT = 7

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
        self.len_lsb = 0
        self.len_msb = 0
        self.data = np.zeros(0x280, dtype=np.uint8)
        self.checksum_lsb = 0
        self.checksum_msb = 0
    
    @property
    def data_length(self):
        return self.len_lsb + self.len_msb * 256
    
    @property
    def checksum(self):
        return self.len_lsb + self.len_msb * 256

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
        self.current_packet = GBPacket()
        self.got_packet = False
        self.rx_byte = 0
        self.tx_byte = 0
        self.num_pages = 0
        self.pages = np.zeros((20, 0x280), dtype=np.uint8)

    def old_gb_interrupt(self, mach):
        bite = mach.get() & 0xFF
        self.bytes_received += 1
        if self.bytes_received % 2:
            mach.put(0x40)
        else:
            mach.put(0x81)
        print(f'Received byte {bite:02x}')

    def gb_interrupt(self, mach):
        self.rx_byte = mach.get() & 0xFF
        # print(f'IRQ Received byte {self.rx_byte:02x}')
        # print(f'Had sent {self.tx_byte:02x}')
        self.process_byte()
    
    def startup(self):
        self.sm.irq(self.gb_interrupt)
        self.sm.active(1)
        self.sm.put(0x00)
        self.run()
    
    def run(self):
        while True:
            while not self.got_packet:
                pass
            print(f'Packet type: {self.current_packet.command} Packet data: {1}')
            if self.current_packet.command == 4:
                pass
                self.pages[self.num_pages,:] = self.current_packet.data
                self.num_pages += 1
            self.got_packet = False
            
    def process_byte(self):
        done = False
        # print(f'Received byte {self.rx_byte:02x}')
        # print(f"State is {self.state}")
        self.tx_byte = 0x00

        if self.state == STATE_IDLE:
            self.tx_byte = 0x00
            if self.rx_byte == 0x88:
                self.state = STATE_MAGICBYTES_PARTIAL
                # print('pre here!')

        elif self.state == STATE_MAGICBYTES_PARTIAL:
            if self.rx_byte == 0x33:
                self.state = STATE_HEADER
                self.remaining_bytes = 4
                # print('Received magic bytes!')
            else:
                self.state = STATE_IDLE

        elif self.state == STATE_HEADER:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 3:
                self.current_packet.command = self.rx_byte
            elif self.remaining_bytes == 2:
                self.current_packet.compression_flag = self.rx_byte
            elif self.remaining_bytes == 1:
                self.current_packet.len_lsb = self.rx_byte
            else:
                self.current_packet.len_msb = self.rx_byte
                # print('Received header!')
                # print(f"Packet is type {self.current_packet.command}")
                if self.current_packet.data_length:
                    self.state = STATE_PAYLOAD
                    self.remaining_bytes = self.current_packet.data_length
                else:
                    # print(f"Packet is dataless")
                    self.state = STATE_DATASUM
                    self.remaining_bytes = 2
        
        elif self.state == STATE_PAYLOAD:
            idx = self.current_packet.data_length - self.remaining_bytes
            self.remaining_bytes -= 1
            self.current_packet.data[idx] = self.rx_byte
            if self.remaining_bytes == 0:
                # print('Done collecting data bytes')
                self.state = STATE_DATASUM
                self.remaining_bytes = 2
        
        elif self.state == STATE_DATASUM:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 1:
                self.current_packet.checksum_lsb = self.rx_byte
            else:
                self.current_packet.checksum_msb = self.rx_byte
                # print("Received checksum!")
                self.state = STATE_DATASUM_DONE
                self.tx_byte = 0x81 # first response byte
        
        elif self.state == STATE_DATASUM_DONE:
            self.state = STATE_RESPONSE_PARTIAL
            self.tx_byte = 0x00 # should be actual status

        elif self.state == STATE_RESPONSE_PARTIAL:
            self.state = STATE_IDLE
            self.got_packet = True

        self.sm.put(self.tx_byte)
        


link = GBLink()
link.startup()


