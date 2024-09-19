"""Super Game Boy Printer"""

from lcd_i2c import LCD
from machine import I2C, Pin
import utime

import data_buffer
import fake_lcd
import gb_link
import pinout as pin
import pos_link
import timeit

class SuperPrinter():

    def __init__(self):
        try:
            i2c = I2C(1, scl=Pin(27), sda=Pin(26), freq=300000)
            self.lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)
            self.lcd.begin()
        except OSError:
            print('Did not find LCD screen!')
            self.lcd = fake_lcd.FakeLCD()
        self.lcd.clear()
        self.print_logo()

        self.data_buffer = data_buffer.DataBuffer(self.lcd)
        self.gb_link = gb_link.GBLink(self.data_buffer, self.lcd)
        self.pos_link = pos_link.POSLink(
            self.data_buffer, self.lcd, pin.POS_UART, pin.POS_TX, pin.POS_RX
        )
    
    def startup(self):
        try:
            self.gb_link.startup()
            self.pos_link.set_justification(1)
            self.main_loop()
        except (Exception, KeyboardInterrupt) as e:
            self.gb_link.shutdown_pio_mach()
            self.lcd.clear()
            print(dir(e))
            self.lcd.print(e.__class__.__name__)
            raise e
    

    def main_loop(self):
            while True:
                self.last_packet_time = utime.ticks_ms()
                while True:
                    # byte handling done via IRQ
                    self.gb_link.check_handle_packet()
                    if self.gb_link.check_print_ready():
                        self.print()
                    self.gb_link.check_timeout()
    def print(self):
        self.gb_link.shutdown_pio_mach()
        for p in range(self.data_buffer.num_pages):
            print(f'Sending page {p+1} of {self.data_buffer.num_pages}')
            self.data_buffer.convert_page_of_packets(p)
            self.pos_link.send_data_buffer_to_download()
            self.lcd.set_cursor(0, 0)
            self.lcd.print("Printing page...")
            utime.sleep(1)
            self.pos_link.print_download_graphics_data()
            utime.sleep(2)
        self.lcd.clear()
        self.lcd.print("Print complete!")
        utime.sleep(.5)
        self.pos_link.cut()
        self.data_buffer.clear_packets()
        self.gb_link.startup_pio_mach()
    
    gb_chars = [
        [0x1F, 0x10, 0x17, 0x17, 0x17, 0x17, 0x17, 0x00],
        [0x1F, 0x01, 0x1D, 0x1D, 0x1D, 0x1D, 0x1D, 0x00],
        [0x12, 0x17, 0x12, 0x10, 0x11, 0x10, 0x1F, 0x00],
        [0x01, 0x05, 0x09, 0x01, 0x11, 0x03, 0x1E, 0x00]
    ]

    def print_logo(self):
        for i, gb_char in enumerate(self.gb_chars):
            self.lcd.create_char(i, gb_char)
        self.lcd.clear()
        self.lcd.print(chr(0) + chr(1) + ' SUPER')
        self.lcd.set_cursor(0, 1)
        self.lcd.print(chr(2) + chr(3) + ' GB Printer')





if __name__ == "__main__":
    printer = SuperPrinter()
    printer.startup()

  