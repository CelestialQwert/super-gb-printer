from machine import UART, Pin
import time

class PrinterInterface:

    def __init__(self):
        self.uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

    def init_printer(self): 
        self.uart.write(bytes([27, 64]))
        time.sleep(.1)
    
    def print_text(self, text: str):
        text_bytes = bytes(text, 'utf-8')
        self.uart.write(text_bytes)
        self.uart.write(bytes([10])) #line feed
        time.sleep(.1)
        self.print()
        time.sleep(.1)

    def print(self):
        #                      GS   (  L   pL  pH   m  fn
        return self.uart.write(bytes([29, 40, 76,  2,  0, 48, 50]))
    
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
        time.sleep(.1)
    
    def send_download_graphics_data(
        self, full_payload: list[bytearray], x: int, y: int, keycode: str = 'GB', 
    ):
        first_shade_size = len(full_payload[0])
        for shade_payload in full_payload:
            if len(shade_payload) != first_shade_size:
                raise ValueError(
                    'Data for different colors is differene sizes!'
                )

        self.send_download_graphics_data_header(x, y, len(full_payload), keycode)

        print('Sending dl data...')
        for i, shade_payload in enumerate(full_payload):
            print(f"sending tone {i}")
            self.send_tone_number(i)
            self.uart.write(shade_payload)
            time.sleep(.1)
        print('done')

    def send_download_graphics_data_header(
        self, x: int, y: int, num_tones: int=4, keycode: str='GB'
    ):

        if x % 8 or y % 8:
            raise ValueError('Dimensions x and y must be multiple of 8!')

        one_color_size = x * y // 8
        kc1, kc2 = [ord(x) for x in keycode]
        b = num_tones
        a = 48 if b == 1 else 52
        p = 10 + (one_color_size + 1) * b
        p1 = p % 256
        p2 = (p // 256) % 256
        p3 = (p // 65536) % 256
        p4 = (p // 16777216)
        xL = x % 256
        xH = x // 256
        yL = y % 256
        yH = y // 256

        self.uart.write(bytes([
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lparen_cl_fn83.html
        #   GS '8'  L   p1  p2  p3  p4  m   fn  a  kc1  kc2, b, xL, xH, yL, yH
            29, 56, 76, p1, p2, p3, p4, 48, 83, a, kc1, kc2, b, xL, xH, yL, yH
        ]))
    
    def send_tone_number(self, tone: int):
        if tone in [0, 1, 2, 3]:
            tone += 49
        elif tone in [49, 50, 51, 52]:
            pass
        else:
            raise ValueError(f'Invalid tone value {tone}, must be 0-3 or 49-52')
        self.uart.write(bytes([tone]))        
    
    def print_download_graphics_data(self, keycode: str = 'GB', x=1, y=1):
        kc1, kc2 = [ord(x) for x in keycode]
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lparen_cl_fn85.html
        #                      GS   (  L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  6,  0, 48, 85, kc1, kc2, x, y]))
        time.sleep(.1)


    def cut(self, feed_height:int=10):
        # https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_cv.html
        cut_cmd = bytes([
                29, #GS
                86, #V
                65, #m cut type
                feed_height #n feed height
            ]) 
        self.uart.write(cut_cmd)
        time.sleep(.1)