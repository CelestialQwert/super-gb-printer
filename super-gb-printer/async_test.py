import lcd

import _thread
import sys
import utime
import asyncio

import pinout as pinn
import gb_link


def set_global_exception():
    def handle_exception(loop, context):
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)


def main_thread(main_lcd):
    main_lcd.display_title_screen()
    gameboy_link = gb_link.GBLink(in_lcd=main_lcd)
    gameboy_link.startup()
    while True:
        gameboy_link.check_handle_packet()
        gameboy_link.check_timeout()

    
def core_2(main_lcd):
    asyncio.run(async_core_2(main_lcd))


async def async_core_2(main_lcd):
    task = asyncio.create_task(main_lcd.message_loop())
    await run_forever()


async def run_forever():
    while True:
        await asyncio.sleep(0)   


def main():
    set_global_exception()
    main_lcd = lcd.AsyncLCD(scl=pinn.LCD_SCL, sda=pinn.LCD_SDA)
    _thread.start_new_thread(core_2, (main_lcd,))
    main_thread(main_lcd)

main()