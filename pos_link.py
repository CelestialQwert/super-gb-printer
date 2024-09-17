from machine import UART, Pin
from ulab import numpy as np
import utime

import data_buffer
import fake_lcd
import timeit

def wait():
    utime.sleep(.005)

def stretch_with_zero(n, stretch):
    if not n:
        return n
    else:
        return (2**stretch) * stretch_with_zero(n // 2, stretch) + (n % 2)

zoomed_lut = {
    2: np.zeros((256, 2), dtype=np.uint8),
    3: np.zeros((256, 3), dtype=np.uint8),
    4: np.zeros((256, 4), dtype=np.uint8),
}
@timeit.timeit
def make_lut():
    global zoomed_lut, made_lut
    for i in range(256):
        for zoom, single_lut in zoomed_lut.items():
            single_lut[i] = np.frombuffer(
                (stretch_with_zero(i, zoom) * (2**zoom - 1)).to_bytes(zoom, 'big'),
                dtype=np.uint8
            )
    made_lut = True
made_lut = False

class POSLink:

    def __init__(self, buffer=None, lcd=None, tx_pin=0, rx_pin=1):

        self.data_buffer = buffer if buffer else data_buffer.DataBuffer()
        self.lcd = lcd if lcd else fake_lcd.FakeLCD()
        self.uart = UART(0, baudrate=115200, tx=Pin(tx_pin), rx=Pin(rx_pin))
        if not made_lut:
            make_lut()

    def init_printer(self): 
        #                      ESC  @
        self.uart.write(bytes([27, 64]))
        wait()
    
    def set_justification(self, n: int):
        # 0, 48 - left
        # 1, 49 - centered
        # 2, 50 - right
        #                      ESC a  n
        self.uart.write(bytes([27, 97, n]))
        wait()
    
    def print_text(self, text: str):
        text_bytes = bytes(text, 'utf-8')
        self.uart.write(text_bytes + bytes([10])) #append line feed
        wait()
        self.print()

    def print(self):
        #                             GS  (   L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  2,  0, 48, 50]))
        wait()
    
    def send_graphics_data(
        self, payload: bytearray, x: int, y: int, color: int = 0,
        bx: int = 1, by: int = 1
    ):
        a = 48 if color == 0 else 52
        c = 48 + color if color != 0 else 49
        p = 10 + len(payload)
        pL = p % 256
        pH = p // 256
        xL = x % 256
        xH = x // 256
        yL = y % 256
        yH = y // 256

        self.uart.write(bytes(
        #    GS  (   L   pL  pH  m   fn   a  bx  by  c  xL  xH  yL  yH
            [29, 40, 76, pL, pH, 48, 112, a, bx, by, c, xL, xH, yL, yH]
        ))

        self.uart.write(payload)
        wait()
    
    @timeit.timeit
    def send_data_buffer_to_download(self, zoom=3):
        slice_h = self.data_buffer.num_converted_packets * 16
        buffer_slice = [x[:slice_h,:] for x in self.data_buffer.pos_buffer]
        self.send_download_graphics_data(buffer_slice, zoom)
    
    @timeit.timeit
    def send_download_graphics_data(
        self, full_payload: list[np.ndarray], zoom_x: int=1, zoom_y: int=0, 
        keycode: str = 'GB', 
    ):
        first_tone_size = full_payload[0].shape
        for tone_payload in full_payload:
            if tone_payload.shape != first_tone_size:
                raise ValueError('Data for different tones is different sizes!')
        y, x = first_tone_size
        if zoom_y == 0:
            zoom_y = zoom_x

        self.send_download_graphics_data_header(x * zoom_x, y * zoom_y)

        tile_row_buffer = np.zeros(x * zoom_x, dtype=np.uint8)

        tile_row_buffer.copy()

        print('Sending dl data...')
        self.lcd.clear()
        self.lcd.print('Sending')
        for i, tone_payload in enumerate(full_payload):
            print(f"sending tone {i}")
            self.send_tone_number(i)
            for row in range(y):
                if not row % 16:
                    n = (row + i * y) // 16
                    d = y // 4
                    print(f"Packet {n:02}/{d:02}")
                    self.lcd.set_cursor(8, 0)
                    self.lcd.print(f"{n:02}/{d:02}")

                if zoom_x > 1:
                    for px in range(x):
                        tile_row_buffer[px*zoom_x:(px+1)*zoom_x] = (
                            zoomed_lut[zoom_x][tone_payload[row,px]]
                        )
                else:
                    tile_row_buffer = tone_payload[row,:]
                for _ in range(zoom_y):
                    self.uart.write(tile_row_buffer.tobytes())
                    wait()
        print('done')

    def send_download_graphics_data_header(
        self, x: int, y: int, num_tones: int=4, keycode: str='GB'
    ):
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
        if tone in [0, 1, 2, 3]:
            tone += 49
        elif tone in [49, 50, 51, 52]:
            pass
        else:
            raise ValueError(f'Invalid tone value {tone}, must be 0-3 or 49-52')
        self.uart.write(bytes([tone]))
        wait()
    
    def send_download_graphics_data_payload(
        self, one_payload: bytearray, x: int, y: int, zoom_v: int=1, 
    ):
        if x % 8 or y % 8:
            raise ValueError('Dimensions x and y must be multiple of 8!')
        assert len(one_payload) == x * y // 8
    
    def print_download_graphics_data(self, keycode: str = 'GB', x=1, y=1):
        kc1, kc2 = [ord(x) for x in keycode]
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lparen_cl_fn85.html
        #                      GS   (  L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  6,  0, 48, 85, kc1, kc2, x, y]))
        wait()

    def cut(self, feed_height:int=10):
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_cv.html
        cut_cmd = bytes([
                29, #GS
                86, #V
                65, #m cut type
                feed_height #n feed height
            ]) 
        self.uart.write(cut_cmd)
        wait()