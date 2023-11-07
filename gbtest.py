import time
import printer_interface

with open('gbtiles.txt','rb') as f:
    gb_tile = f.read()

# gb_tile = bytearray([
#     0xff, 0x00, 0x7e, 0xff, 0x85, 0x81, 0x89, 0x83, 
#     0x93, 0x85, 0xa5, 0x8b, 0xc9, 0x97, 0x7e, 0xff
# ]*20*9)

from machine import UART, Pin

import printer_interface

WIDTH = 160
ROWS = 12
HEIGHT = ROWS*8
ZOOM = 3
WIDTH_BYTES = WIDTH * ZOOM // 8
PRINTER_BUFFER_SIZE = WIDTH_BYTES * HEIGHT * ZOOM 

GB_BUFFER_SIZE = WIDTH * HEIGHT  // 8

def prep():
    printer_image_buffer = [
        bytearray(PRINTER_BUFFER_SIZE),
        bytearray(PRINTER_BUFFER_SIZE),
        bytearray(PRINTER_BUFFER_SIZE),
        bytearray(PRINTER_BUFFER_SIZE)
    ]
    tone_image_buffer = [
        bytearray(PRINTER_BUFFER_SIZE),
        bytearray(PRINTER_BUFFER_SIZE),
        bytearray(PRINTER_BUFFER_SIZE),
        bytearray(PRINTER_BUFFER_SIZE)
    ]

    num_rows_of_tiles = len(gb_tile) // 320

    # for big_row in range(len(gb_tile) // 320):
    for big_row in range(ROWS):
        print('big row', big_row)
        for tile_idx in range(20):
            for tile_row in range(8):

                byte_pos = big_row*320 + tile_idx*16 + tile_row*2
                lbyte = gb_tile[byte_pos]
                hbyte = gb_tile[byte_pos+1]
                
                llist = [int(x) for x in '{:08b}'.format(lbyte)]
                hlist = [int(x) for x in '{:08b}'.format(hbyte)]

                tlist = [l+2*d for l, d in zip(llist, hlist)]
                # print(tlist)

                row_buffer = [[0]*8, [0]*8, [0]*8, [0]*8]

                for px,tone in enumerate(tlist):
                    row_buffer[tone][px] = 1
                
                for i in range(4):
                    # print(row_buffer[i])
                    print_bytes = 0
                    for px in range(8):
                        print_bytes = print_bytes << ZOOM
                        if row_buffer[i][px]:
                            print_bytes += (2**ZOOM - 1)
                    # print('{:024b}'.format(print_bytes))
                    print_bytearray = print_bytes.to_bytes(ZOOM, 'big')
                    for row in range(ZOOM):
                        start_byte = big_row*ZOOM*WIDTH_BYTES*8 + tile_row*ZOOM*WIDTH_BYTES + row*WIDTH_BYTES + tile_idx*ZOOM
                        tone_image_buffer[i][start_byte:start_byte+3] = print_bytearray
        
        # print('\n')
    
    for byte in range(PRINTER_BUFFER_SIZE):
        printer_image_buffer[0][byte] = tone_image_buffer[2][byte] | tone_image_buffer[3][byte]
        printer_image_buffer[1][byte] = tone_image_buffer[1][byte] | tone_image_buffer[3][byte]
        printer_image_buffer[2][byte] = tone_image_buffer[1][byte] | tone_image_buffer[3][byte]
        printer_image_buffer[3][byte] = tone_image_buffer[1][byte] | tone_image_buffer[3][byte]
    

    return printer_image_buffer

def main():

    big_image_buffer = prep()

    printface = printer_interface.PrinterInterface()
    
    printface.send_download_graphics_data(big_image_buffer, WIDTH*ZOOM, HEIGHT*ZOOM)
    printface.print_download_graphics_data()

    printface.cut()


if __name__ == '__main__':
    print('hello!')
    main()