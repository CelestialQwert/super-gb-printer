
import asyncio
import _thread
import sys
import utime

import data_buffer
import gb_link
import lcd
import pinout as pinn

def set_global_exception():
    def handle_exception(context):
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)


def main_thread(main_lcd, main_data_buffer):
    main_lcd.display_title_screen()
    gameboy_link = gb_link.GBLink(in_lcd=main_lcd, in_buffer=main_data_buffer)
    gameboy_link.startup()
    while True:
        gameboy_link.check_handle_packet()
        gameboy_link.check_timeout()

    
def core_2(main_lcd, main_data_buffer):
    asyncio.run(async_core_2(main_lcd, main_data_buffer))


async def async_core_2(main_lcd, main_data_buffer):
    message_task = main_lcd.message_loop()
    convert_task = main_data_buffer.convert_loop()
    # main_data_buffer.sync_convert_loop()
    await asyncio.gather(message_task, convert_task)


def main():
    set_global_exception()
    main_lcd = lcd.AsyncLCD(scl=pinn.LCD_SCL, sda=pinn.LCD_SDA)
    main_data_buffer = data_buffer.DataBuffer(main_lcd)
    _thread.start_new_thread(core_2, (main_lcd, main_data_buffer))
    main_thread(main_lcd, main_data_buffer)

main()