import asyncio 
from machine import I2C

from lcd_i2c import LCD
from threadsafe import ThreadSafeQueue


gb_chars = [
    [0x1F, 0x10, 0x17, 0x17, 0x17, 0x17, 0x17, 0x00],
    [0x1F, 0x01, 0x1D, 0x1D, 0x1D, 0x1D, 0x1D, 0x00],
    [0x12, 0x17, 0x12, 0x10, 0x11, 0x10, 0x1F, 0x00],
    [0x01, 0x05, 0x09, 0x01, 0x11, 0x03, 0x1E, 0x00]
]


backslash = [0, 0x10, 0x08, 0x04, 0x02, 0x01, 0, 0]


class AsyncLCD():
    """Contains an LCD and ways to pass messages to display asynchronously.
    
    Messages are also printed to stdout in case no LCD is present.
    """
    
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
            self.is_real_lcd = False
        self.lcd.clear()

        self._queue = ThreadSafeQueue(20)
    
    def display_title_screen(self) -> None:
        if self.is_real_lcd:
            self.lcd.clear()
            self.lcd.print(chr(0) + chr(1) + ' SUPER')
            self.lcd.set_cursor(0, 1)
            self.lcd.print(chr(2) + chr(3) + ' GB PRINTER')
        print('To LCD: <Insert title screen here>')
    
    def queue_message(
            self, message: str, col: int = 0, row: int = 0, 
            erase: bool = True
        ) -> None:
        """Add a message to the queue to be displayed on the LCD screen.
        
        Args:
            message: The message to display
            col: Starting column for the message (0-15)
            row: Row for the message (0 or 1)
            erase: Erase the display before printing message
        """
        self._queue.put_sync((message, col, row, erase))

    async def message_loop(self) -> None:
        """Displays messages on the LCD as they come in."""
        async for message, col, row, erase in self._queue:
            if erase:
                self.lcd.clear()
                print(f"For LCD: {message}")
            else:
                print(f"For LCD (no erase): {message}")
            if row or col:
                self.lcd.set_cursor(row, col)
            self.lcd.print(message)
            await asyncio.sleep(0)
    
    # passthrough methods 

    def begin(self):
        if self.is_real_lcd:
            self.lcd.begin()

    def clear(self):
        if self.is_real_lcd:
            self.lcd.clear()

    def print(self, text: str):
        if self.is_real_lcd:
            self.lcd.print(text)
        print(f"To LCD: {text}")

    def set_cursor(self, *args, **kwargs):
        if self.is_real_lcd:
            self.lcd.set_cursor(*args, **kwargs)

    def create_char(self, *args, **kwargs):
        if self.is_real_lcd:
            self.lcd.create_char(*args, **kwargs)
