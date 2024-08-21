from ulab import numpy as np
import utime
import rp2
import uctypes

i = 69

NUM_TESTS = 1
t = 0
for j in range(NUM_TESTS):
    st = utime.ticks_us()
    en = utime.ticks_us()
    t += en-st
avg = t / NUM_TESTS
print(f"Average time for time check: {avg} us")



ls = [0]*0x280
st = utime.ticks_us()
ls[0] = i
# ls[1] = i
en = utime.ticks_us()
print(f"List time: {en-st} us")



arr = np.zeros(0x280, dtype=np.uint8)
st = utime.ticks_us()
arr[0] = i.to_bytes(1, 'little')
en = utime.ticks_us()
print(f"Bytes array time: {en-st} us")



st = utime.ticks_us()
arr[0] = i
en = utime.ticks_us()
print(f"Array time: {en-st} us")



st = utime.ticks_us()
ls2 = ls.copy()
en = utime.ticks_us()
print(f"Dupe time: {en-st} us")



b = bytearray(0x280)
st = utime.ticks_us()
b[0:10] = b'aaaa'
en = utime.ticks_us()
print(f"Array init time: {en-st} us")



PACKET_DATA = {
    "MAGIC_BYTES": (0x00 | uctypes.ARRAY, 0x02 | uctypes.UINT8),
    "HEADER_TYPE": 0x02 | uctypes.UINT8,
    "HEADER_COMPRESSION": 0x03 | uctypes.UINT8,
    "HEADER_PACKET_SIZE": 0x04 | uctypes.UINT16,
}
pck = bytearray(6)
packet = uctypes.struct(uctypes.addressof(pck), PACKET_DATA)



a = bytearray(32)
b = bytearray(32)
d = rp2.DMA()
c = d.pack_ctrl()  # Just use the default control value.
# The count is in 'transfers', which defaults to four-byte words, so divide length by 4
st = utime.ticks_us()
d.config(read=a, write=b, count=len(a)//4, ctrl=c, trigger=True)
# Wait for completion
while d.active():
    pass
en = utime.ticks_us()
print(f"DMA time: {en-st} us")


PACKET_DATA = {
    "MAGIC_BYTES": (0x00 | uctypes.ARRAY, 0x02 | uctypes.UINT8),
    "HEADER_TYPE": 0x02 | uctypes.UINT8,
    "HEADER_COMPRESSION": 0x03 | uctypes.UINT8,
    "HEADER_PACKET_SIZE": 0x04 | uctypes.UINT16,
}
pck = bytearray(6)

packet = uctypes.struct(uctypes.addressof(pck), PACKET_DATA)

class GBPacket:
    def __init__(self):
        self.raw_data = bytearray(6)
    
    @property
    def header_type(self):
        return self.raw_data[2]
    
gb_packet = GBPacket()

st = utime.ticks_us()
h1 = packet.HEADER_TYPE
en = utime.ticks_us()
print(f"Struct time: {en-st} us")

st = utime.ticks_us()
h2 = gb_packet.header_type
en = utime.ticks_us()
print(f"Class time: {en-st} us")