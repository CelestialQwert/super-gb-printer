from machine import I2C, Pin
from lcd_i2c import LCD
import time
import _thread

import pinout as pinn
import super_printer

def main() -> None:
    try:
        _thread.start_new_thread(lcd_thread, ())
        main_thread()
    except BaseException as e:
        print(f"Got exception '{e}'!")
        _thread.exit()
        raise

def lcd_thread() -> None:
    i2c = I2C(1, scl=pinn.LCD_SCL, sda=pinn.LCD_SDA, freq=300000)
    lcd = LCD(addr=0x27, cols=16, rows=2, i2c=i2c)
    lcd.begin()

    gb_chars = [
        [0x1F, 0x10, 0x17, 0x17, 0x17, 0x17, 0x17, 0x00],
        [0x1F, 0x01, 0x1D, 0x1D, 0x1D, 0x1D, 0x1D, 0x00],
        [0x12, 0x17, 0x12, 0x10, 0x11, 0x10, 0x1F, 0x00],
        [0x01, 0x05, 0x09, 0x01, 0x11, 0x03, 0x1E, 0x00]
    ]

    backslash = [0, 0x10, 0x08, 0x04, 0x02, 0x01, 0, 0]

    for i, gb_char in enumerate(gb_chars):
        lcd.create_char(i, gb_char)
    lcd.create_char(4, backslash)

    lcd.clear()
    lcd.print(chr(0) + chr(1) + ' SUPER')
    lcd.set_cursor(0, 1)
    lcd.print(chr(2) + chr(3) + ' Cool printr')

    time.sleep(.2)

    while True:
        for c in ['/', '-', chr(4), '|']:
            lcd.set_cursor(14,0)
            lcd.print(c)
            time.sleep(.5)

def light_thread() -> None:
    lights = [Pin(x, Pin.OUT) for x in range(6, 9)]
    for lit in lights:
        lit.off()
    while True:
        for lit in lights:
            lit.toggle()
            time.sleep(.25)
    
def main_thread() -> None:
    printer = super_printer.SuperPrinter()
    printer.run()

if __name__ == "__main__":
    main()