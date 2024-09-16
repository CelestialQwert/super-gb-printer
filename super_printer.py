"""Super Game Boy Printer"""

from lcd_i2c import LCD
from machine import I2C, Pin
import utime

import data_buffer
import gb_link
import fake_lcd
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

        self.data_buffer = data_buffer.DataBuffer()
        self.gb_link = gb_link.GBLink(self.data_buffer, self.lcd)
    
    def startup(self):
        self.lcd.print('Super GB Printer')
        self.gb_link.startup()
        self.gb_link.run()


if __name__ == "__main__":
    printer = SuperPrinter()
    printer.startup()