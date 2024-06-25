import rp2

import time
import rp2
from machine import Pin

@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    set_init=rp2.PIO.OUT_HIGH,
    # sideset_init=rp2.PIO.OUT_LOW
)
def gb_link():
    wrap_target()
    set(x, 6)
    wait(0, gpio, 0)   # wait for falling edge
    set(pins, 0)
    pull(noblock)         # pull value for transmission from pico
    out(null, 24)         # shift left by 24
    mov(y, osr) #@@@@@@@
    out(pins, 1)[2]       # out the MSB bit
    wait(1, gpio, 0)[2]   # wait for rising edge
    label("bitloop")      
    in_(pins, 1)          # input bit
    wait(0, gpio, 0)[2]   # wait for falling edge
    out(pins, 1)          # output rest of the bits one by one
    wait(1, gpio, 0)[1]   # wait for rising edge
    jmp(x_dec, "bitloop") # loop through the rest of the bits
    in_(pins, 1)          # input rest of the bits one by one
    in_(y, 8) #@@@@@@
    push(noblock)         # push the received value to pico
    irq(rel(0))
    wrap()

# Instantiate a state machine with the blink program, at 2000Hz, with set bound to Pin(25) (LED on the Pico board)
sm = rp2.StateMachine(
    0, gb_link, 
    in_base=Pin(1),
    out_base=Pin(2),
    set_base=Pin(25),
    sideset_base=Pin(25)
)


def gb_interrupt(mach):
    bite = mach.get() & 0xFFFF
    mach.put(0x81)
    print(f'Received byte {bite:04x}')

sm.irq(gb_interrupt)
sm.active(1)

while True:
    pass