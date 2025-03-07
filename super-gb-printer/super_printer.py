"""Super Game Boy Printer

Main script for the Super GB Printer. Will eventually get called main.py
when this whole thing is done.
"""

from machine import Pin
import utime

import data_buffer
import lcd
import gb_link
import pinout as pinn
import pos_link
import pin_manager
import utimeit



class SuperPrinter():
    """Top level class for the printer.
    
    Contains instances of all the child classes needed to run the printer,
    and handles tasks that involve most/all of those child classes.
    """

    def __init__(self) -> None:
        """Instantiate the class."""

        self.btn = pin_manager.PinManager()

        self.lcd = lcd.setup_lcd(scl=pinn.LCD_SCL, sda=pinn.LCD_SDA)
        self.print_logo()

        self.data_buffer = data_buffer.DataBuffer(self.lcd)
        self.gb_link = gb_link.GBLink(self)
        self.pos_link = pos_link.POSLink(self.data_buffer, self.lcd)
    
    def run(self) -> None:
        """The method to run after instantiatng a SuperPrinter."""

        try:
            self.gb_link.startup()
            self.pos_link.init_printer()
            self.main_loop()
        except (Exception, KeyboardInterrupt) as e:
            self.gb_link.shutdown_pio_mach()
            self.lcd.clear()
            Pin(pinn.GB_LED_ACTIVITY, Pin.OUT).off()
            Pin(pinn.GB_PIO_ENABLED, Pin.OUT).off()
            Pin(pinn.POS_TX_ACTIVITY, Pin.OUT).off()
            print(dir(e))
            self.lcd.print(e.__class__.__name__)
            raise e
    
    def main_loop(self) -> None:
        """The main loop.

        Runs continuously, checking if certain things are ready.
        """

        while True:
            self.last_packet_time = utime.ticks_ms()
            while True:
                # byte handling done via PIO and IRQ method in gb_link
                self.gb_link.check_handle_packet()
                if self.gb_link.check_print_ready():
                    self.print()
                self.gb_link.check_timeout()

    def print(self) -> None:
        """Runs a print job.

        Shuts down the GB link PIO while running so any Game Boy software
        will immediately throw an error while the print is processing.
        
        Does the following tasks:
        - Converts the incoming GB tile data to the POS printer format
        - Sends data to the printer, enlarging it as needed
        - Send print and cut paper commands to the printer

        If there is more than 18 packets of data, it is processed, sent, and
        printed in "pages" of 18 packets, then cut at the end.
        """

        self.gb_link.shutdown_pio_mach()
        print('Commencing print')
        self.pos_link.set_justification(1)
        if self.btn.no_scale:
            zoom = 1
        elif self.btn.scale_2x:
            zoom = 2
        else:
            zoom = 3
        for p in range(self.data_buffer.num_pages):
            print(f'Sending page {p+1} of {self.data_buffer.num_pages}')
            num_pkts = self.data_buffer.convert_page_of_packets(p)
            self.pos_link.send_data_buffer_to_download(zoom)
            self.lcd.set_cursor(0, 0)
            self.lcd.print("Printing page...")
            self.pos_link.print_download_graphics_data(zoom)
            utime.sleep(.15 * num_pkts)
        self.lcd.clear()
        self.lcd.print("Print complete!")
        utime.sleep(.5)
        if self.btn.add_bottom_margin:
            self.pos_link.cut(feed_height=184)
        else:
            self.pos_link.cut()
        self.gb_link.startup_pio_mach(keep_message=True)
    
    gb_chars = [
        [0x1F, 0x10, 0x17, 0x17, 0x17, 0x17, 0x17, 0x00],
        [0x1F, 0x01, 0x1D, 0x1D, 0x1D, 0x1D, 0x1D, 0x00],
        [0x12, 0x17, 0x12, 0x10, 0x11, 0x10, 0x1F, 0x00],
        [0x01, 0x05, 0x09, 0x01, 0x11, 0x03, 0x1E, 0x00]
    ]

    def print_logo(self) -> None:
        """Prints logo to LCD screen.
        
        Intended to run at startup, it sends the above custom character data
        (a small Game Boy pic) to the LCD and displays it and the title.
        """

        for i, gb_char in enumerate(self.gb_chars):
            self.lcd.create_char(i, gb_char)
        self.lcd.clear()
        self.lcd.print(chr(0) + chr(1) + ' SUPER')
        self.lcd.set_cursor(0, 1)
        self.lcd.print(chr(2) + chr(3) + ' GB Printer')


if __name__ == "__main__":
    printer = SuperPrinter()
    printer.run()
  