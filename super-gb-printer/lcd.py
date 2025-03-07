from typing import Union
from lcd_i2c import LCD
from machine import I2C

class FakeLCD():
    """Fake LCD class for when the screen isn't available.
    
    Most methods do nothing, but the print method redirects to stdout.
    """
    def __init__(self):
        pass

    def begin(self):
        pass

    def clear(self):
        pass

    def print(self, text: str):
        print(f"To LCD: {text}")

    def set_cursor(self, *args, **kwargs):
        pass

    def create_char(self, *args, **kwargs):
        pass

def setup_lcd(scl: int = 0, sda: int = 0) -> Union[LCD, FakeLCD]:

    try:
        i2c = I2C(1, scl=scl, sda=sda, freq=300000)
        lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)
        lcd.begin()
    except OSError:
        print('Did not find LCD screen!')
        lcd = FakeLCD()
    lcd.clear()
    return lcd