import time
import utime
from collections import namedtuple
from machine import UART, Pin
from ulab import numpy as np

import printer_interface

# gb_tile = bytearray([
#     0xff, 0x00, 0x7e, 0xff, 0x85, 0x81, 0x89, 0x83, 
#     0x93, 0x85, 0xa5, 0x8b, 0xc9, 0x97, 0x7e, 0xff
# ]*20*18)


TILES_PER_BIG_ROW = 20
ROWS_PER_TILE = 8
BYTES_PER_ROW = 2
BYTES_PER_TILE = ROWS_PER_TILE * BYTES_PER_ROW
BYTES_PER_BIG_ROW = TILES_PER_BIG_ROW * BYTES_PER_TILE

PIXELS_PER_ROW = 8

WIDTH = 160
BIG_ROWS = 36
TILE_HEIGHT = 8
BITS_PER_BYTE = 8
ZOOM = 3
ZOOM_V = 3
HEIGHT = BIG_ROWS * TILE_HEIGHT
WIDTH_BYTES = WIDTH * ZOOM // BITS_PER_BYTE
PRINTER_BUFFER_SIZE = WIDTH_BYTES * HEIGHT * ZOOM_V
GB_BUFFER_SIZE = WIDTH * HEIGHT // BITS_PER_BYTE

WHITE = 0
LIGHTGRAY = 1
DARKGRAY = 2
BLACK = 3

"""
conversions between color and tone

white - 0
lightgray - 7 (1/2/4)
darkgray - 9 (1/8)
black - 15 (1/2/4/8)

tone 49 (8) - black, darkgray, lightgray
tone 50 (4) - black, lightgray
tone 51 (2) - black, lightgray
tone 52 (1) - black, darkgray
"""

def timeit(f, *args, **kwargs):
    func_name = str(f).split(' ')[1]
    def new_func(*args, **kwargs):
        t = utime.ticks_us()
        result = f(*args, **kwargs)
        micros = utime.ticks_diff(utime.ticks_us(), t)
        print(f'execution time: {micros/1000000} s')
        return result
    return new_func

ToneImageBuffer = namedtuple(
    'ToneImageBuffer',
    ['tone49', 'tone50', 'tone51', 'tone52']
)

tib_shape = (HEIGHT, WIDTH_BYTES)

tone_image_buffer = ToneImageBuffer(
    np.zeros(tib_shape, dtype=np.uint8), # tone 49, value 8
    np.zeros(tib_shape, dtype=np.uint8), # tone 50, value 4
    np.zeros(tib_shape, dtype=np.uint8), # tone 51, value 2
    np.zeros(tib_shape, dtype=np.uint8)  # tone 52, value 1
)

def zoom_with_zero(n):
    if not n:
        return n
    else:
        return (2**ZOOM) * zoom_with_zero(n // 2) + (n % 2)

zoomed_lut = np.zeros((256,ZOOM), dtype=np.uint8)
for i in range(256):
    zoomed_lut[i] = np.frombuffer(
        (zoom_with_zero(i) * 7).to_bytes(3, 'big'),
        dtype=np.uint8
    )
# print(zoomed_lut)
# crash

@timeit
def prep(gb_tile):

    num_rows_of_tiles = gb_tile.shape[0] // BYTES_PER_BIG_ROW

    for big_row in range(num_rows_of_tiles): # iterate over rows of tiles
        print('big row', big_row)
        for tile_idx in range(TILES_PER_BIG_ROW): # then each tile
            tile_pos = (
                    big_row * BYTES_PER_BIG_ROW
                    + tile_idx * BYTES_PER_TILE
                )
            
            # each row is two bytes, little endian
            lbytes = gb_tile[tile_pos     : tile_pos + BYTES_PER_TILE     : 2]
            hbytes = gb_tile[tile_pos + 1 : tile_pos + BYTES_PER_TILE + 1 : 2]
            
            # white     = ~lbytes & ~hbytes
            lightgray_tile =  lbytes & ~hbytes
            darkgray_tile  = ~lbytes &  hbytes
            black_tile     =  lbytes &  hbytes

            tiles = [lightgray_tile, darkgray_tile, black_tile]

            lightgray_zoomed =  np.zeros((8, ZOOM), dtype=np.uint8)
            darkgray_zoomed =  np.zeros((8, ZOOM), dtype=np.uint8)
            black_zoomed =  np.zeros((8, ZOOM), dtype=np.uint8)

            for r in range(ROWS_PER_TILE):
                lightgray_zoomed[r] = zoomed_lut[lightgray_tile[r]]
                darkgray_zoomed[r] = zoomed_lut[darkgray_tile[r]]
                black_zoomed[r] = zoomed_lut[black_tile[r]]
            
            tone49_tile = black_zoomed | darkgray_zoomed 
            tone50_tile = black_zoomed | lightgray_zoomed 
            tone51_tile = black_zoomed | lightgray_zoomed 
            tone52_tile = black_zoomed | darkgray_zoomed | lightgray_zoomed 

            trow = big_row * ROWS_PER_TILE
            tcol = tile_idx * ZOOM

            tone_image_buffer.tone49[trow:trow+8, tcol:tcol+3] = tone49_tile
            tone_image_buffer.tone50[trow:trow+8, tcol:tcol+3] = tone50_tile
            tone_image_buffer.tone51[trow:trow+8, tcol:tcol+3] = tone51_tile
            tone_image_buffer.tone52[trow:trow+8, tcol:tcol+3] = tone52_tile

        
def main():

    with open('certificate.bin', 'rb') as f:
        pic = np.frombuffer(f.read(), dtype=np.uint8)

    printface = printer_interface.PrinterInterface()
    
    prep(pic)

    printface.init_printer()
    printface.set_justification(1)
    printface.send_download_graphics_data(
        tone_image_buffer, WIDTH*ZOOM, HEIGHT, ZOOM_V)
    printface.print_download_graphics_data()

    printface.cut()


if __name__ == '__main__':
    print('hello!')
    main()