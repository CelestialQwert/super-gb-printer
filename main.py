from machine import UART, Pin
import random
import time

ROWS = 32
# gfx = bytearray([0]*(ROWS*64))
# for y in range(ROWS):
#     for x in range(64):
#         i = y*64+x
#         if (y%16 > 7):
#             gfx[i] = 255 if (x%2) else 0
#         else:
#             gfx[i] = 0 if (x%2) else 255
gfx = bytearray([0]*(ROWS*64))
for y in range(ROWS):
    for x in range(64):
        i = y*64+x
        gfx[i] = 255 if (x % 8) > 3 else 0



TONE_ROWS = 64
tones = [
    bytearray([0]*(TONE_ROWS*64)),
    bytearray([0]*(TONE_ROWS*64)),
    bytearray([0]*(TONE_ROWS*64)),
    bytearray([0]*(TONE_ROWS*64)),
]

for t in range(4):
    for y in range(TONE_ROWS):
        for x in range(64):
            i = y*64+x
            tones[t][i] = 255 if (x % (8<<t)) > ((4<<t) - 1) else 0

LIGHT = bytearray([0]*(TONE_ROWS*64))
DARK = bytearray([255]*(TONE_ROWS*64))
    

class Printer:

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
    

    def cut(self, feed_height:int=10):
        cut_cmd = bytes([
                29, #GS
                86, #V
                65, #m cut type
                feed_height #n feed height
            ]) 
        self.uart.write(cut_cmd)

def main():
    printer = Printer()
    printer.print_text('Hello there!\n\n')
    printer.print_text('123456789012345678901234567890123456789012\n')
    printer.print_text('              5     7  8                 F\n')
    time.sleep(.1)

    printer.send_graphics_data(gfx, 512, ROWS)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    for t, tone in enumerate(tones):
        print(t)
        printer.send_graphics_data(tone, 512, TONE_ROWS, color=4-t)
        time.sleep(.1)
    printer.print()
    time.sleep(.1)

    #print light stripe
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=4)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    #print medium stripe
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=3)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=4)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    #print dark stripe
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=1)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=3)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=4)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)


    #print white stripe
    printer.send_graphics_data(LIGHT, 512, TONE_ROWS, color=1)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    #print light stripe
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=4)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    #print medium stripe
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=1)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    #print dark stripe
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=1)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=3)
    time.sleep(.1)
    printer.send_graphics_data(DARK, 512, TONE_ROWS, color=4)
    time.sleep(.1)
    printer.print()
    time.sleep(.1)

    printer.cut()


if __name__ == '__main__':
    main()