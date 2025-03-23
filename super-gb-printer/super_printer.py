"""Super Game Boy Printer

Main script for the Super GB Printer. Will eventually get called main.py
when this whole thing is done.
"""

import asyncio
from machine import Pin
import sys
import utime
import _thread

import data_buffer
import lcd
import gb_link
import pinout as pinn
import pos_link
import pin_manager
import utimeit

class ThreadException(Exception):
    pass

class SuperPrinter():
    """Top level class for the printer.
    
    Contains instances of all the child classes needed to run the printer,
    and handles tasks that involve most/all of those child classes.
    """

    def __init__(self) -> None:
        """Instantiate the class."""

        self.settings = pin_manager.DIPManager()
        self.btn = pin_manager.ButtonManager()
        self.leds = pin_manager.LEDManager()

        self.lcd = lcd.AsyncLCD(scl=pinn.LCD_SCL, sda=pinn.LCD_SDA)
        self.lcd.display_title_screen()

        self.data_buffer = data_buffer.DataBuffer(self.lcd, self.settings)
        self.gb_link = gb_link.GBLink(
            self.data_buffer, self.lcd, self.leds)
        self.pos_link = pos_link.POSLink(
            self.data_buffer, self.lcd, self.settings, self.leds
        )

        self.thread_exception = ""

    def core_2(self):
        asyncio.run(self.async_core_2())
    
    async def async_core_2(self):
        message_task = self.lcd.message_loop()
        convert_task = self.data_buffer.convert_loop()
        print_task = self.pos_link.pos_loop()
        manual_cut_task = self.pos_link.manual_cut_loop()
        try:
            await asyncio.gather(
                message_task, convert_task, print_task, manual_cut_task
            )
        except Exception as e:
            self.thread_exception = e.__class__.__name__
            raise e
    
    def run(self) -> None:
        """The method to run after instantiatng a SuperPrinter."""

        _thread.start_new_thread(self.core_2, ())
        self.gb_link.startup()
        try:
            while True:
                self.gb_link.check_handle_packet()
                self.gb_link.check_timeout()
                if self.thread_exception:
                    raise ThreadException
        except (Exception, KeyboardInterrupt) as e:
            self.gb_link.shutdown_pio_mach()
            self.lcd.clear()
            if isinstance(e, ThreadException):
                self.lcd.print(self.thread_exception)
            else:
                self.lcd.print(e.__class__.__name__)
            self.leds.all_off()
            raise e


if __name__ == "__main__":
    printer = SuperPrinter()
    printer.run()
  