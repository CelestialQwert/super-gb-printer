# code to be run in micropython

import utime
from ulab import numpy as np
import random


@timeit
def py_bits(twobyte):
    for i in range(8):
        # each row is two bytes, little endian
        lbyte = twobyte[2*i]
        hbyte = twobyte[2*i+1]
        
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
        
        for c in range(1, 4):
            print_bytes = 0
            for px in range(8):
                print_bytes = print_bytes << 3
                if row_buffer[c][px]:
                    print_bytes += (7)
            print_bytearray = print_bytes.to_bytes(3, 'big')

u16 = np.zeros(8, dtype=np.uint16)

@timeit
def np_bits(twobyte, trips):
    # each row is two bytes, little endian
    lbytes = data[::2]
    hbytes = data[1::2]
    
    # white     = ~lbytes & ~hbytes
    lightgray =  lbytes & ~hbytes
    darkgray  = ~lbytes &  hbytes
    black     =  lbytes &  hbytes

    # black_16 = black
    # black_16 = black + u16

    for color in [lightgray, darkgray, black]:
        for i in range(8):
            t = trips[color[i]]

    # for color in [lightgray, darkgray, black]:
    #     for i in range(8):
    #         t = np.frombuffer(
    #             (triple_zero(color[i]) * 7).to_bytes(3, 'big'),
    #             dtype=np.uint8
    #         )

@timeit
def generate_triple_lut():
    triple_lut = np.zeros((256,3), dtype=np.uint8)
    for i in range(256):
        triple_lut[i] = np.frombuffer(
            (triple_zero(i) * 7).to_bytes(3, 'big'),
            dtype=np.uint8
        )
    return triple_lut

def triple_zero(n):
    if not n:
        return n
    else:
        return 8 * triple_zero(n // 2) + (n % 2)

data = np.array([random.randint(0,255) for x in range(16)], dtype=np.uint8)
bytedata = data.tobytes()

trips = generate_triple_lut()

py_bits(bytedata)
np_bits(data, trips)

