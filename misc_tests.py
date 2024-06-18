from machine import UART, Pin

import printer_interface

ROWS = 32
gfx = bytearray([0]*(ROWS*64))
for y in range(ROWS):
    for x in range(64):
        i = y*64+x
        gfx[i] = 255 if (x % 8) > 3 else 0

TONE_ROWS = 32
tones = [
    bytearray(TONE_ROWS*64),
    bytearray(TONE_ROWS*64),
    bytearray(TONE_ROWS*64),
    bytearray(TONE_ROWS*64),
]

for t in range(4):
    for y in range(TONE_ROWS):
        for x in range(64):
            i = y*64+x
            tones[3-t][i] = 255 if (x % (8<<t)) > ((4<<t) - 1) else 0

LIGHT = bytearray([0]*(TONE_ROWS*64))
DARK = bytearray([255]*(TONE_ROWS*64))

def main():
    printface = printer_interface.PrinterInterface()
    printface.print_text('Hello there!\n\n')
    printface.print_text('123456789012345678901234567890123456789012\n')
    printface.print_text('              5  6  7  8                 F\n')

    printface.send_graphics_data(gfx, 512, ROWS)
    printface.print()

    printface.send_download_graphics_data(tones, 512, TONE_ROWS)
    printface.print_download_graphics_data()

    #print white stripe
    printface.send_graphics_data(LIGHT, 512, TONE_ROWS, color=1)
    printface.print()

    #print light stripe
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=3)
    printface.print()

    #print medium stripe
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=1)
    printface.print()

    #print dark stripe
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=1)
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=2)
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=3)
    printface.send_graphics_data(DARK, 512, TONE_ROWS, color=4)
    printface.print()

    printface.cut()


if __name__ == '__main__':
    main()