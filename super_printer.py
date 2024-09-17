"""Super Game Boy Printer"""

from lcd_i2c import LCD
from machine import I2C, Pin
import utime

import data_buffer
import gb_link
import fake_lcd
import pos_link
import timeit

class SuperPrinter():

    def __init__(self):
        try:
            i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=300000)
            self.lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)
            self.lcd.begin()
        except OSError:
            print('Did not find LCD screen!')
            self.lcd = fake_lcd.FakeLCD()
        self.lcd.clear()
        self.lcd.print('Super GB Printer')

        self.data_buffer = data_buffer.DataBuffer(self.lcd)
        self.gb_link = gb_link.GBLink(self.data_buffer, self.lcd)
        self.pos_link = pos_link.POSLink(self.data_buffer, self.lcd)
    
    def startup(self):
        self.gb_link.startup()
        self.pos_link.set_justification(1)
        self.main_loop()

    def main_loop(self):
        try:
            while True:
                self.last_packet_time = utime.ticks_ms()
                while True:
                    # byte handling done via IRQ
                    self.gb_link.check_handle_packet()
                    if self.gb_link.check_print_ready():
                        self.print()
                    self.gb_link.check_timeout()
        except KeyboardInterrupt as e:
            self.gb_link.shutdown_pio_mach()
            self.lcd.clear()
            raise e
    
    def print(self):
        self.gb_link.shutdown_pio_mach()
        num_pages = ((self.data_buffer.num_packets - 1) // 18) + 1
        for p in range(num_pages):
            print(f'Sending page {p+1} of {num_pages}')
            p_low = p*18
            p_hi = min((p+1)*18, self.data_buffer.num_packets)
            self.data_buffer.convert_packet_range(p_low, p_hi)
            self.pos_link.send_data_buffer_to_download()
            utime.sleep(1)
            self.pos_link.print_download_graphics_data()
            utime.sleep(1)
        utime.sleep(.5)
        self.pos_link.cut()
        self.lcd.clear()
        self.lcd.print(f"Done")
        self.data_buffer.clear_packets()
        self.gb_link.startup_pio_mach()


if __name__ == "__main__":
    printer = SuperPrinter()
    printer.startup()