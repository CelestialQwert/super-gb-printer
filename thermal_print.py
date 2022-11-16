from machine import UART, Pin
import random
ROWS = 100

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
uart.write(b'Hello there!\n\n')

# store_gfx_command = bytes([
#     29, # GS
#     40, # (
#     76, # L
#     (10 + ROWS*64) % 256, # pL payload size low byte
#     (10 + ROWS*64) // 256, # pH payload size hi byte
#     48, #m 
#     112,#fn
#     48, #a monochrome (48) or multitone (52)
#     1, #bx horizontal stretch 1x/2x
#     1, #by vertical stretch 1x/2x
#     49, #c color (49-52)
#     0, #xL width low byte
#     2, #xH width high byte
#     ROWS % 256, #yL length low byte
#     ROWS // 256  #yH length high byte
# ])


# gfx = bytearray([0]*(ROWS*64))

# for y in range(ROWS):
#     for x in range(64):
#         i = y*64+x
#         if (y%16 > 7):
#             gfx[i] = 255 if (x%2) else 0
#         else:
#             gfx[i] = 0 if (x%2) else 255

store_gfx_command = bytes([
    29, # GS
    40, # (
    76, # L
    (10 + ROWS) % 256, # pL payload size low byte
    (10 + ROWS) // 256, # pH payload size hi byte
    48, #m 
    112,#fn
    48, #a monochrome (48) or multitone (52)
    1, #bx horizontal stretch 1x/2x
    1, #by vertical stretch 1x/2x
    49, #c color (49-52)
    6, #xL width low byte
    0, #xH width high byte
    ROWS % 256, #yL length low byte
    ROWS // 256  #yH length high byte
])

gfx = bytearray([0b10010011]*(ROWS))

uart.write(store_gfx_command)
uart.write(gfx)

print_cmd = bytes([
    29, # GS
    40, # (
    76, # L
    2, # pL
    00, # pH
    48, # m
    50, # fn
])

uart.write(print_cmd)

cut_cmd = bytes([
    29, #GS
    86, #V
    65, #m cut type
    10 #n feed height
])
print(uart.write(cut_cmd))
