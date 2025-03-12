import lcd

import _thread
import sys
import utime
import asyncio

import pinout as pinn

def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

def main_thread(main_lcd):
    messages = [
        'Hello world!',
        'How are you', 
        'Goodbye!'
    ]
    while True:
        for msg in messages:
            main_lcd.send_message(msg)
            utime.sleep(.2)
            utime.sleep(1.3)
    
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