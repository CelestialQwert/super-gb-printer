from machine import UART, Pin
import time

class PrinterInterface:

    def __init__(self):
        self.uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
    
    def print_text(self, text: str):
        text_bytes = bytes(text, 'utf-8')
        self.uart.write(text_bytes)

    def print(self):
        #                      GS   (  L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  2,  0, 48, 50]))
    
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
        self, payload: list[bytearray], x: int, y: int, keycode: str = 'GB', 
    ):
        first_shade_size = len(payload[0])
        for shade_payload in payload:
            if len(shade_payload) != first_shade_size:
                raise ValueError(
                    'Data for different colors is differene sizes!'
                )
        kc1, kc2 = [ord(x) for x in keycode]
        b = len(payload)
        a = 48 if b == 1 else 52
        p = 10 + (first_shade_size + 1) * b
        p1 = p % 256
        p2 = (p // 256) % 256
        p3 = (p // 65536) % 256
        p4 = (p // 16777216)
        xL = x % 256
        xH = x // 256
        yL = y % 256
        yH = y // 256

        self.uart.write(bytes([
        #   GS '8'  L   p1  p2  p3  p4  m   fn  a  kc1  kc2, b, xL, xH, yL, yH
            29, 56, 76, p1, p2, p3, p4, 48, 83, a, kc1, kc2, b, xL, xH, yL, yH
        ]))

        print('Sending dl data...')
        for i, shade_payload in enumerate(payload):
            print(i)
            self.uart.write(bytes([49+i]))
            self.uart.write(shade_payload)
            time.sleep(.1)
        print('done')
    
    def print_download_graphics_data(self, keycode: str = 'GB', x=1, y=1):
        kc1, kc2 = [ord(x) for x in keycode]
        #                      GS   (  L   pL  pH   m  fn
        self.uart.write(bytes([29, 40, 76,  6,  0, 48, 85, kc1, kc2, x, y]))
        time.sleep(.1)


    def cut(self, feed_height:int=10):
        cut_cmd = bytes([
                29, #GS
                86, #V
                65, #m cut type
                feed_height #n feed height
            ]) 
        self.uart.write(cut_cmd)