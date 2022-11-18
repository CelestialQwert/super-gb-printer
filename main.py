from machine import UART, Pin

import printer_interface

#(160*144 image) * (3*3 scale) // (8 px per byte) * (4 shades)
ONE_BUFFER_SIZE = 25920
big_image_buffer = [
    bytearray(ONE_BUFFER_SIZE),
    bytearray(ONE_BUFFER_SIZE),
    bytearray(ONE_BUFFER_SIZE),
    bytearray(ONE_BUFFER_SIZE)
]
# final_image_buffer = bytearray(ONE_BUFFER_SIZE)

#(160*144 image) * (2 bit per pixel) // (8 bit per byte)
GB_TILE_BUFFER_SIZE = 5760
gb_tile_buffer = bytearray(GB_TILE_BUFFER_SIZE)

#(160*144 image)
GB_BUFFER_SIZE = 23040
gb_image_buffer = bytearray(GB_BUFFER_SIZE)

print('making buffer data...')
for t in range(4):
    print(t)
    for i in range(ONE_BUFFER_SIZE):
        big_image_buffer[t][i] = i+(25*t)
print('done')

def main():
    printface = printer_interface.PrinterInterface()
    
    printface.send_download_graphics_data(big_image_buffer, 160*3, 144*3)
    printface.print_download_graphics_data()

    printface.cut()


if __name__ == '__main__':
    print('hello!')
    main()