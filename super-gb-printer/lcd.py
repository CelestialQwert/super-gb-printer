import asyncio 

from machine import I2C
from typing import Union

from lcd_i2c import LCD
from threadsafe import ThreadSafeQueue

class FakeLCD():
    """Fake LCD class for when the real display isn't available.
    
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
    """Setup a real LCD display, or failing that create a fake one."""

    try:
        i2c = I2C(1, scl=scl, sda=sda, freq=300000)
        lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)
        lcd.begin()
    except OSError:
        print('Did not find LCD screen!')
        lcd = FakeLCD()
    lcd.clear()
    return lcd

AnyLCD = Union[LCD, FakeLCD]

gb_chars = [
    [0x1F, 0x10, 0x17, 0x17, 0x17, 0x17, 0x17, 0x00],
    [0x1F, 0x01, 0x1D, 0x1D, 0x1D, 0x1D, 0x1D, 0x00],
    [0x12, 0x17, 0x12, 0x10, 0x11, 0x10, 0x1F, 0x00],
    [0x01, 0x05, 0x09, 0x01, 0x11, 0x03, 0x1E, 0x00]
]

backslash = [0, 0x10, 0x08, 0x04, 0x02, 0x01, 0, 0]

class AsyncLCD():
    """Contains an LCD and ways to pass messages to display asynchronously."""
    
    def __init__(self, scl: int = 0, sda: int = 0) -> None:
        try:
            self.i2c = I2C(1, scl=scl, sda=sda, freq=300000)
            self.lcd = LCD(addr=0x27, cols=16, rows=2, i2c=self.i2c)
            self.lcd.begin()
            for i, gb_char in enumerate(gb_chars):
                self.lcd.create_char(i, gb_char)
            self.lcd.create_char(4, backslash)
            self.is_real_lcd = True
        except (ValueError, OSError):
            print('Did not find LCD screen!')
            self.lcd = FakeLCD()
            self.is_real_lcd = False
        self.lcd.clear()

        self._queue = ThreadSafeQueue(68)
    
    def display_title_screen(self) -> None:
        if self.is_real_lcd:
            self.lcd.clear()
            self.lcd.print(chr(0) + chr(1) + ' SUPER')
            self.lcd.set_cursor(0, 1)
            self.lcd.print(chr(2) + chr(3) + ' Cool printr')
        else:
            print('<Insert title screen here>')
    
    def queue_message(self, message: str) -> None:
        self._queue.put_sync(message)

    async def message_loop(self) -> None:
        async for msg in self._queue:
            self.lcd.clear()
            self.lcd.print(msg)
            await asyncio.sleep(0)

    def begin(self):
        self.lcd.begin()

    def clear(self):
        self.lcd.clear()

    def print(self, text: str):
       self.lcd.print(text)

    def set_cursor(self, *args, **kwargs):
        self.lcd.set_cursor(*args, **kwargs)

    def create_char(self, *args, **kwargs):
        self.lcd.create_char(*args, **kwargs)
