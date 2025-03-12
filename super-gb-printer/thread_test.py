import time
import _thread

import pinout as pinn
import gb_link
import lcd

def main() -> None:
    try:
        _thread.start_new_thread(lcd_thread, ())
        main_thread()
    except BaseException as e:
        print(f"Got exception '{e.__class__.__name__}'!")
        _thread.exit()
        raise

def lcd_thread() -> None:
    main_lcd = lcd.AsyncLCD(scl=pinn.LCD_SCL, sda=pinn.LCD_SDA)

    main_lcd.lcd_title_screen()

    time.sleep(.2)

    while True:
        for c in ['/', '-', chr(4), '|']:
            main_lcd.lcd.set_cursor(14,0)
            main_lcd.lcd.print(c)
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
    gameboy_link = gb_link.GBLink()
    gameboy_link.startup()
    while True:
        gameboy_link.check_handle_packet()
        gameboy_link.check_timeout()

if __name__ == "__main__":
    main()