import time
import printer_interface


# gb_tile = bytearray([
#     0xff, 0x00, 0x7e, 0xff, 0x85, 0x81, 0x89, 0x83, 
#     0x93, 0x85, 0xa5, 0x8b, 0xc9, 0x97, 0x7e, 0xff
# ]*20*18)

from machine import UART, Pin

import printer_interface

TILES_PER_BIG_ROW = 20
ROWS_PER_TILE = 8
BYTES_PER_ROW = 2
BYTES_PER_TILE = ROWS_PER_TILE * BYTES_PER_ROW
BYTES_PER_BIG_ROW = TILES_PER_BIG_ROW * BYTES_PER_TILE

PIXELS_PER_ROW = 8

WIDTH = 160
BIG_ROWS = 18
TILE_HEIGHT = 8
BITS_PER_BYTE = 8
ZOOM = 3
ZOOM_V = 3
HEIGHT = BIG_ROWS * TILE_HEIGHT
WIDTH_BYTES = WIDTH * ZOOM // BITS_PER_BYTE
PRINTER_BUFFER_SIZE = WIDTH_BYTES * HEIGHT * ZOOM_V
GB_BUFFER_SIZE = WIDTH * HEIGHT // BITS_PER_BYTE
print('buffer size', PRINTER_BUFFER_SIZE)

WHITE = 0
LIGHTGRAY = 1
DARKGRAY = 2
BLACK = 3

tone_image_buffer = [
    bytearray(PRINTER_BUFFER_SIZE), # value 8
    bytearray(PRINTER_BUFFER_SIZE), # value 4
    bytearray(PRINTER_BUFFER_SIZE), # value 2
    bytearray(PRINTER_BUFFER_SIZE)  # value 1
]
color_image_buffer = [
    bytearray(1),                   # WHITE (buffer not needed)
    bytearray(PRINTER_BUFFER_SIZE), # LIGHT GRAY
    bytearray(PRINTER_BUFFER_SIZE), # DARK GRAY 
    bytearray(PRINTER_BUFFER_SIZE)  # BLACK
]


def prep(gb_tile):

    num_rows_of_tiles = len(gb_tile) // BYTES_PER_BIG_ROW

    for big_row in range(BIG_ROWS): # iterate over rows of tiles
        print('big row', big_row)
        for tile_idx in range(TILES_PER_BIG_ROW): # then each tile
            for tile_row in range(ROWS_PER_TILE): # then each row in a tile

                # find location of byte to process in gb tile data
                byte_pos = (
                    big_row * BYTES_PER_BIG_ROW
                    + tile_idx * BYTES_PER_TILE
                    + tile_row * BYTES_PER_ROW
                )

                # each row is two bytes, little endian
                lbyte = gb_tile[byte_pos]
                hbyte = gb_tile[byte_pos + 1]
                
                # refactor into list of 8 pixels, 0 (white) to 3 (black)
                llist = [int(x) for x in '{:08b}'.format(lbyte)]
                hlist = [int(x) for x in '{:08b}'.format(hbyte)]
                tlist = [l+2*h for l, h in zip(llist, hlist)]

                # make a buffer of 8 pixels for each of the 4 colors
                row_buffer = [[0]*8, [0]*8, [0]*8, [0]*8]

                # for each pixel, mark the corresponding pixel in that color 
                # buffer
                for px, color in enumerate(tlist):
                    row_buffer[color][px] = 1
                
                # loop over the three non-white colors to turn each pixel 
                # buffer into a bytearray with a length equal to horiz zoom
                for c in range(1, 4):
                    print_bytes = 0
                    for px in range(PIXELS_PER_ROW):
                        print_bytes = print_bytes << ZOOM
                        if row_buffer[c][px]:
                            print_bytes += (2**ZOOM - 1)
                    print_bytearray = print_bytes.to_bytes(ZOOM, 'big')
                    # loop once for each vertical zoom
                    for row in range(ZOOM_V):
                        # find location of row pixels in color buffer
                        start_byte = (
                            big_row * ZOOM_V * WIDTH_BYTES * ROWS_PER_TILE
                            + tile_row * ZOOM_V * WIDTH_BYTES 
                            + row * WIDTH_BYTES 
                            + tile_idx * ZOOM
                        )
                        # add the pixels to that color buffer
                        color_image_buffer[c][start_byte:start_byte+ZOOM] = print_bytearray
    
    for byte in range(PRINTER_BUFFER_SIZE): 
        tone_image_buffer[0][byte] = (
            color_image_buffer[DARKGRAY][byte] 
            | color_image_buffer[BLACK][byte]
        )
        tone_image_buffer[1][byte] = (
            color_image_buffer[LIGHTGRAY][byte] 
            | color_image_buffer[BLACK][byte]
        )
        tone_image_buffer[2][byte] = (
            color_image_buffer[LIGHTGRAY][byte] 
            | color_image_buffer[BLACK][byte]
        )
        tone_image_buffer[3][byte] = (
            color_image_buffer[LIGHTGRAY][byte] 
            | color_image_buffer[DARKGRAY][byte] 
            | color_image_buffer[BLACK][byte]
        )

        
def main():

    with open('bulbasaur.bin', 'rb') as f:
        pic1 = f.read()
    with open('bulbasaur2.bin', 'rb') as f:
        pic2 = f.read()

    printface = printer_interface.PrinterInterface()
    
    for pic in [pic1]:
        prep(pic)
        
        printface.send_download_graphics_data(
            tone_image_buffer, WIDTH * ZOOM, HEIGHT * ZOOM_V)
        printface.print_download_graphics_data()

    printface.cut()


if __name__ == '__main__':
    print('hello!')
    main()