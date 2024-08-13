from machine import Pin
from ulab import numpy as np

data = np.zeros(256, dtype=np.uint8)
d = 0

clk = Pin(0, Pin.IN, Pin.PULL_DOWN)
rx = Pin(1, Pin.IN)
# tx = Pin(2, Pin.IN)

def clk_low(pin):
    global data, d
    data[d] = rx.value()
    d += 1
    print(f'clocked {d}')

clk.irq(clk_low)

print('start!')
while True:
    pass