import rp2
import utime
import uctypes

@rp2.asm_pio(out_shiftdir=rp2.PIO.SHIFT_LEFT)
def push_numbers(): 
    set(x, 0)
    label("loopie")
    set(y, 0xA)
    in_(y, 4)
    set(y, 0xA)
    in_(y, 4)
    set(y, 0xB)
    in_(y, 4)
    set(y, 0xB)
    in_(y, 4)
    set(y, 0xC)
    in_(y, 4)
    set(y, 0xC)
    in_(y, 4)
    set(y, 0xD)
    in_(y, 4)
    set(y, 0xD)
    in_(y, 4)
    jmp(x_dec, "loopie")
    push(noblock)


sm = rp2.StateMachine(0, push_numbers, freq=int(1e6))
sm.active(1)

st = utime.ticks_us()
a = sm.get()
en = utime.ticks_us()
print(f"Pio time: {en-st} us")
