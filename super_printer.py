"""Super Game Boy Printer"""

from lcd_i2c import LCD
from machine import I2C, Pin
import utime

import data_buffer
import gb_link
import timeit

class FakeLCD():
    """Fake LCD class for when the screen isn't available."""
    def __init__(self):
        pass

    def begin(self):
        pass

    def clear(self):
        pass

    def print(self, text: str):
        print(f"To LCD: {text}")

class SuperPrinter():

    def __init__(self):
        try:
            i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=300000)
            self.lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)
            self.lcd.begin()
        except OSError:
            print('Did not find LCD screen!')
            self.lcd = FakeLCD()
        self.lcd.clear()

        self.data_buffer = data_buffer.DataBuffer()
        self.gb_link = gb_link.GBLink(self.data_buffer)
    
    def startup(self):
        self.lcd.print('Hello!')
        self.gb_link.startup()
        self.gb_link.run()


if __name__ == "__main__":
    printer = SuperPrinter()
    printer.startup()