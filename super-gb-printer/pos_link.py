"""Class POSLink

Contains methods for communicating with the POS printer, including 
configuring settings and sending data and commands. 

Currently tested with the Epson TM-T88V, but the TM-T88VI and TM-T88VII will
probably work too. 

Printing makes use of the download graphics buffer inside the printer. It's 
large emough to hold 2 screens (18 packets, 36 tile rows) of graphics data 
converted to the printer's graphics format at 3x zoom and multi-tone 
(16 colors, but only 4 get used). 
"""

import utime
from machine import UART, Pin
from micropython import const
from typing import Optional, Union
from ulab import numpy as np

import data_buffer
import fake_lcd
import lcd_i2c
import pinout as pinn
import utimeit

ROWS_PER_PACKET = const(16)


def wait():
    r"""Add a small wait time after a POS serial transmission.
    
    For some reason it makes the data connection more stable ¯\_ (ツ)_/¯
    """
    utime.sleep(.005)


class POSLink:
    """POS Interface.
    
    Contains methods for communicating with the POS printer, including 
    configuring settings and sending data and commands.
    """

    AnyLCD = Union[lcd_i2c.LCD, fake_lcd.FakeLCD, None]

    def __init__(
            self, 
            buffer: Optional[data_buffer.DataBuffer] = None,
            lcd: AnyLCD = None,
        ) -> None:
        """Instantiate the class.
        
        Args:
            buffer: DataBuffer instance
            lcd: LCD instance for an optional attached LCD screen
        """

        self.data_buffer = buffer if buffer else data_buffer.DataBuffer()
        self.lcd = lcd if lcd else fake_lcd.FakeLCD()
        self.uart = UART(
            0, baudrate=115200, tx=Pin(pinn.POS_TX), rx=Pin(pinn.POS_RX))
        self.activity_led = Pin(pinn.POS_TX_ACTIVITY, Pin.OUT)
        self.zoomed_lut = {
            2: np.zeros((256, 2), dtype=np.uint8),
            3: np.zeros((256, 3), dtype=np.uint8),
            4: np.zeros((256, 4), dtype=np.uint8),
        }
        self.make_lut()

    def make_lut(self) -> None:
        """Creates look-up table for stretching out bits in a byte.

        Used to "zoom" an image sent to the POS printer by stretching out its
        bytes.
        
        Example:
            Input: 10010110 (150)
            Output for 3x zoom: 111000000111000111111000

        TODO: Make this a fixed LUT rather than computed at runtime?
        """
        for i in range(256):
            for zoom, single_lut in self.zoomed_lut.items():
                single_lut[i] = np.frombuffer(
                    (self.stretch(i,zoom) * (2**zoom-1)).to_bytes(zoom,'big'),
                    dtype=np.uint8
                )
    
    @staticmethod
    def stretch(n, zoom) -> int:
        """The algorithm for making the zoom LUT."""
        if not n:
            return n
        else:
            return (2**zoom) * POSLink.stretch(n // 2, zoom) + (n % 2)


    def init_printer(self) -> None:
        """Send printer init command."""
        self.activity_led.off()
        #                      ESC  @
        self.uart.write(bytes([27, 64]))
        wait()
    
    def set_justification(self, n: int) -> None:
        """Send printer alignment command.
        
        Args:
            n: Alignment, one of the following values:
                0, 48 - left
                1, 49 - centered
                2, 50 - right
        """
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/esc_la.html
        #                      ESC a  n
        self.uart.write(bytes([27, 97, n]))
        wait()
    
    def print_text(self, text: str) -> None:
        """Send text to the printer, then print command."""

        text_bytes = bytes(text, 'utf-8')
        self.uart.write(text_bytes + bytes([10])) #append line feed
        wait()
        self.print()

    def print(self):
        """Send print command."""
        #                      GS  (   L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  2,  0, 48, 50]))
        wait()
    
    @utimeit.timeit
    def send_data_buffer_to_download(self, zoom: int = 3):
        """Send portion of data buffer containing data to printer.

        Args:
            zoom: Zoom level of the image
        """

        slice_h = self.data_buffer.num_converted_packets * ROWS_PER_PACKET
        buffer_slice = [x[:slice_h,:] for x in self.data_buffer.pos_buffer]
        self.send_download_graphics_data(buffer_slice, zoom)
    
    def send_download_graphics_data(
        self, full_payload: list[np.ndarray], zoom_x: int = 1, 
        zoom_y: int = -1, keycode: str = 'GB', 
    ):
        """Send data in printer data format to the printer.
        
        Args:
            full_payload: 
                A list of four numpy arrays containg data for each tone
            zoom_x: Zoom in horizontal direction
            zoom_y: Zoon in verical direction (why not let it be different)
            keycode: Code that the data is stored under inside printer
        
        TODO: Have 2x zoom just send data as-is and use internal
            zoom feature of printer
        """

        # check if each tone data array is the same size
        first_tone_size = full_payload[0].shape
        for tone_payload in full_payload:
            if tone_payload.shape != first_tone_size:
                raise ValueError(
                    'Data for different tones is different sizes!'
                )
        y, x = first_tone_size
        
        #check zoom levels
        if zoom_y == -1:
            zoom_y = zoom_x

        # Phys zoom - How much the image is scaled before being sent to 
        # the printer. At zoom = 2, the print is not resized and the printer
        # handles scaling it
        phys_zoom_x = 1 if zoom_x < 3 else zoom_x
        phys_zoom_y = 1 if zoom_y < 3 else zoom_y

        # POS zoom - tells the printer to do the scaling when zoom = 2
        pos_zoom_x = 2 if zoom_x == 2 else 1
        pos_zoom_y = 2 if zoom_y == 2 else 1

        # send header
        self.send_download_graphics_data_header(
            x * phys_zoom_x, y * phys_zoom_y, keycode=keycode
        )

        # Tell everyone we're about to start sending data
        print('Sending download data...')
        self.lcd.clear()
        self.lcd.print('Sending')
        if self.data_buffer.num_pages > 1:
            self.lcd.set_cursor(0, 1)
            cp = self.data_buffer.current_page
            nump = self.data_buffer.num_pages
            self.lcd.print(f"Page {cp}/{nump}")
        
        # start sending data
        tile_row_buffer = np.zeros(x * phys_zoom_x, dtype=np.uint8)
        for i, tone_payload in enumerate(full_payload):
            print(f"sending tone {i}")
            self.send_tone_number(i)
            for row in range(y):
                # update the LCD with each packet (16 px tall) processed
                if not row % 16:
                    n = (row + i * y) // 16
                    d = y // 4
                    self.lcd.set_cursor(8, 0)
                    self.lcd.print(f"{n:02}/{d:02}")
                if phys_zoom_x >= 3:
                    for px in range(x):
                        # stretch each byte by amout of x-zoom
                        tile_row_buffer[px*phys_zoom_x:(px+1)*phys_zoom_x] = (
                            self.zoomed_lut[phys_zoom_x][tone_payload[row,px]]
                        )
                else:
                    # if not zoomed, just send the row data
                    tile_row_buffer = tone_payload[row,:]
                self.activity_led.on()
                for _ in range(phys_zoom_y):
                    # need to send y times to create y-zoom
                    self.uart.write(tile_row_buffer.tobytes())
                    wait()
                self.activity_led.off()
        print('done')

    def send_download_graphics_data_header(
        self, x: int, y: int, num_tones: int = 4, keycode: str = 'GB'
    ):
        """Send the header portion of the send download graphics data command.
        
        Args:
            x: Horizontal dimension of data
            y: Vertical dimension of data
            num_tones: Number of tones passed through to printer
            keycode: Code that the data is stored under inside printer
        """
        one_color_size = x * y 
        kc1, kc2 = [ord(x) for x in keycode]
        b = num_tones
        a = 48 if b == 1 else 52
        p = 10 + (one_color_size + 1) * b
        p1 = p % 256
        p2 = (p // 256) % 256
        p3 = (p // 65536) % 256
        p4 = (p // 16777216)
        xL = (x*8) % 256
        xH = (x*8) // 256
        yL = y % 256
        yH = y // 256

        self.uart.write(bytes([
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lparen_cl_fn83.html
        #   GS '8'  L   p1  p2  p3  p4  m   fn  a  kc1  kc2, b, xL, xH, yL, yH
            29, 56, 76, p1, p2, p3, p4, 48, 83, a, kc1, kc2, b, xL, xH, yL, yH
        ]))
        wait()
    
    def send_tone_number(self, tone: int):
        """Send tone number, converted to range 49-52 as the printer likes.

        Run as part of a send download graphics data command.

        Args:
            tone: The tone number, 0-3 or 49-52 
        """
        if tone in [0, 1, 2, 3]:
            tone += 49
        elif tone in [49, 50, 51, 52]:
            pass
        else:
            raise ValueError(f'Invalid tone value {tone}, must be 0-3 or 49-52')
        self.uart.write(bytes([tone]))
        wait()
    
    def print_download_graphics_data(
            self, zoom_x: int = 1, zoom_y: int = -1, keycode: str = 'GB'
        ):
        """Send the header portion of the send download graphics data command.
        
        Args:
            zoom_x: Horizontal zoom of data, 1 or 2
            zoom_y: Vertical zoom of data, 1 or 2
            keycode: Code that the data is stored under inside printer
        """
        if zoom_y == -1:
            zoom_y = zoom_x
        
        x = 2 if zoom_x == 2 else 1
        y = 2 if zoom_y == 2 else 1
        
        kc1, kc2 = [ord(x) for x in keycode]
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lparen_cl_fn85.html
        #                      GS   (  L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  6,  0, 48, 85, kc1, kc2, x, y]))
        wait()

    def cut(self, feed_height: int = 0):
        """Send command to cut the paper.
        
        Args:
            fed_height: 
                Height of bottom margin before cut in increments of 
                1/360 inches (that 360 is adjustable with GS P command).
                A feed height of 184 is ~13 mm, plus the ~2 mm margin always
                present after a cut, gives the same 15 mm margin that the top
                of the print has (margin between cut and print heads).
        """
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_cv.html
        #                      GS  V   m   n
        self.uart.write(bytes([29, 86, 65, feed_height]))
        wait()