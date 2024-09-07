from machine import UART, Pin

import printer_interface

def gb_prep():
#(160*144 image) * (2 bit per pixel) // (8 bit per byte)
    GB_TILE_BUFFER_SIZE = 5760
    gb_tile_buffer = bytearray(GB_TILE_BUFFER_SIZE)

    #(160*144 image)
    GB_BUFFER_SIZE = 23040
    gb_image_buffer = bytearray(GB_BUFFER_SIZE)



#(160*144 image) * (3*3 scale) // (8 px per byte) 
# one array for each of 4 shades
ONE_BUFFER_SIZE = 25920
# test - 512x128
ONE_BUFFER_SIZE = 512 * 64 // 8

def prep():
    big_image_buffer = [
        bytearray(ONE_BUFFER_SIZE),
        bytearray(ONE_BUFFER_SIZE),
        bytearray(ONE_BUFFER_SIZE),
        bytearray(ONE_BUFFER_SIZE)
    ]
    # final_image_buffer = bytearray(ONE_BUFFER_SIZE)

    print('making buffer data...')
    # for t in range(4):
    #     print(t)
    #     for i in range(ONE_BUFFER_SIZE):
    #         # big_image_buffer[t][i] = i+(25*t)
    #         if (i+1) % 4 == t:
    #             big_image_buffer[t][i] = 255
    #         else:
    #             big_image_buffer[t][i] = 0

    isize = ONE_BUFFER_SIZE//16

    for t in range(4):
        print(t)
        for b in range(16):
            for i in range(isize):
                # if i * 16 // 15 > isize:
                #     big_image_buffer[t][b*isize+i] = 0
                if (b >> (3-t))%2:
                    big_image_buffer[t][b*isize+i] = 255
                else:
                    big_image_buffer[t][b*isize+i] = 0

    print('done')
    return big_image_buffer

def main():

    big_image_buffer = prep()

    printface = printer_interface.PrinterInterface()
    
    # printface.send_download_graphics_data(big_image_buffer, 160*3, 144*3)
    printface.send_download_graphics_data(big_image_buffer, 512, 64)
    printface.print_download_graphics_data()

    printface.cut()


if __name__ == '__main__':
    print('hello!')
    main()