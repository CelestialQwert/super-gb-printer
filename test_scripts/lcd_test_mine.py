from lcd_i2c import LCD
from machine import I2C, Pin
import utime

# define custom I2C interface, default is 'I2C(0)'
# check the docs of your device for further details and pin infos
# this are the pins for the Raspberry Pi Pico adapter board
i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=300000)
lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)

# get LCD infos/properties
print(f"LCD is on I2C address {lcd.addr:02x}")
print(f"LCD has {lcd.cols} columns and {lcd.rows} rows")
print(f"LCD is used with a charsize of {lcd.charsize}")
print(f"Cursor position is {lcd.cursor_position}")

lcd.begin()
utime.sleep(.5)

st = utime.ticks_us()
lcd.print("Hello World")
en = utime.ticks_us()
print(f"LCD time: {en-st} us")

st = utime.ticks_us()
lcd.print("Hello World 1234567890123456789012345678901234567890")
en = utime.ticks_us()
print(f"Long LCD time: {en-st} us")

st = utime.ticks_us()
lcd.print("A")
en = utime.ticks_us()
print(f"Short LCD time: {en-st} us")

st = utime.ticks_us()
lcd.clear()
lcd.print("Hello World")
en = utime.ticks_us()
print(f"LCD clear and print time: {en-st} us")

st = utime.ticks_us()
print("Hello World")
en = utime.ticks_us()
print(f"stdout time: {en-st} us")

st = utime.ticks_us()
lcd.set_cursor(10, 0)
lcd.print(str(12))
en = utime.ticks_us()
print(f"LCD set nubmer time: {en-st} us")