"""GBLink Class

Contains methods that handle the connection to the Game Boy.
"""

import asyncio
import rp2
import utime
from machine import Pin
from micropython import const
from typing import Optional
# from ulab import numpy as np

import data_buffer
import lcd
import pinout as pinn
import pin_manager
import utimeit

# Add type hints for the rp2.PIO Instructions
# VS Code thinks the module is imported
# Actual code will have TYPE_CHECKING = False to prevent the import
from typing_extensions import TYPE_CHECKING # type: ignore
if TYPE_CHECKING:
    from rp2.asm_pio import *

# states for handling the incoming GB packet
STATE_IDLE = const(0)
STATE_MAGICBYTES_PARTIAL = const(1)
STATE_HEADER = const(2)
STATE_PAYLOAD = const(3)
STATE_CHECKSUM = const(4)
STATE_RESPONSE_READY = const(5)
STATE_RESPONSE_PARTIAL = const(6)
STATE_TIMEOUT = const(7)

# commands in the GB packets
COMMAND_INIT = const(1)
COMMAND_PRINT = const(2)
COMMAND_DATA = const(4)
COMMAND_BREAK = const(8)
COMMAND_STATUS = const(0xF)

# status values for GB printer
PRINTER_IDLE = const(0)
PRINTER_READY_TO_PRINT = const(8)
PRINTER_PRINTING = const(6)
PRINTER_COMPLETE = const(4)

# PIO program for interacing with Game Boy
@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    set_init=rp2.PIO.OUT_LOW,
    out_init=rp2.PIO.OUT_LOW,
)
def gb_link_pio():
    set(x, 6)             # set loop to run 6 + 1 times
    wait(0, gpio, 2)      # wait for falling edge
    # set(pins, 1)          # byte started, turn on LED
    pull(noblock)         # pull value from TX FIFO to OSR
    out(null, 24)         # shift left by 24, keeping 8 bits of desired data
    out(pins, 1)          # out the MSB bit in OSR to GB
    wait(1, gpio, 2)[2]   # wait for rising edge
    label("loop")      
    in_(pins, 1)          # MSB input bit from GB to ISR
    wait(0, gpio, 2)[2]   # wait for falling edge
    out(pins, 1)          # output the next bit from OSR to GB
    wait(1, gpio, 2)[1]   # wait for rising edge
    jmp(x_dec, "loop")    # loop through the rest of the bits
    in_(pins, 1)          # input last bit from GB
    push(noblock)         # push the received value from ISR to RX FIFO
    irq(rel(0))           # set interrupt
    # set(pins, 0)          # byte complete, turn off LED

class GBLink:
    """Contains methods that handle the connection to the Game Boy."""

    def __init__(
            self,
            in_buffer: Optional[data_buffer.DataBuffer] = None,
            in_lcd: Optional[lcd.AsyncLCD] = None,
            in_leds: Optional[pin_manager.LEDManager] = None
        ):
        """Instantiate the class."""

        self.data_buffer = in_buffer if in_buffer else data_buffer.DataBuffer()
        self.lcd = in_lcd if in_lcd else lcd.AsyncLCD()
        self.leds = in_leds if in_leds else pin_manager.LEDManager()
        self.pio_mach = rp2.StateMachine(
            0, gb_link_pio, 
            in_base=Pin(pinn.GB_IN),
            out_base=Pin(pinn.GB_OUT),
            # set_base=Pin(pinn.GB_LED_ACTIVITY),
            freq = int(1e6)
        )
        self.packet_state = STATE_IDLE
        self.remaining_bytes = 0
        self.packet = data_buffer.GBPacket()
        self.byte_received = False
        self.complete_packet = False
        self.rx_byte = 0
        self.tx_byte = 0
        self.printer_status = PRINTER_IDLE
        self.end_of_print_data = False
        self.last_packet_time = utime.ticks_ms()
        self.fake_print_ticks = 0
        
        self.fake_printing = False

    def startup(self) -> None:
        """Initialize the GB link."""

        self.leds.pio_enabled.off()
        # Pin(pinn.GB_LED_ACTIVITY, Pin.OUT).off()
        self.pio_mach.irq(self.gb_interrupt)
        self.shutdown_pio_mach()
        self.startup_pio_mach(keep_message=True)
        print('gb link ready!')
    
    def shutdown_pio_mach(self) -> None:
        """Shut down link PIO and clean out FIFOs."""

        # print('Shutting down PIO')
        self.pio_mach.active(0)
        self.leds.pio_enabled.off()
        self.leds.gb_activity.off()
        while self.pio_mach.rx_fifo():
            print('Draining RX FIFO')
            _ = self.pio_mach.get()
        while self.pio_mach.tx_fifo():
            print('Draining TX FIFO')
            self.pio_mach.exec('pull(noblock)')
            self.pio_mach.exec('out(null, 32)')

    def startup_pio_mach(self, keep_message: bool = False) -> None:
        """Start up link PIO and add initial status byte 0."""
        
        #print('Starting PIO')
        self.pio_mach.restart()
        self.leds.pio_enabled.on()
        self.initialize_emu_printer()
        if not keep_message:
            self.lcd.queue_message('Ready', timestamp=True)
        self.pio_mach.active(1)
        # self.pio_mach.put(0)
        self.last_packet_time = utime.ticks_ms()
    
    def check_timeout(self) -> None:
        """Check if the GB link has timed out.
        
        Timeout is 3 seconds, after which the PIO is restarted, the current
        packet and data buffer is discarded, and some other things are reset.
        """
        this_time = utime.ticks_ms()
        if (utime.ticks_diff(this_time, self.last_packet_time) > 3000):
            self.shutdown_pio_mach()
            self.startup_pio_mach()
        
    def initialize_emu_printer(self) -> None:
        """Resets states/buffers related to the emulated printer."""

        self.packet_state = STATE_IDLE
        self.printer_status = PRINTER_IDLE
        self.data_buffer.clear_packets()
    
    def check_ready_to_convert(self) -> bool:
        """Checks if a print is ready to start.

        Check succeeds if a print command packet has been received from the
        Game Boy and at least one second has passed since the last incoming
        packet, to ensure the Game Boy is no longer sending status commands
        during the fake print period (see check_handle_packet). 

        Returns:
            True or False if print is (not) ready.
        """
        this_time = utime.ticks_ms()
        if (
            utime.ticks_diff(this_time, self.last_packet_time) > 1000
            and self.end_of_print_data
        ):
            self.end_of_print_data = False
            return True
        return False

    def gb_interrupt(self, pio_mach: rp2.StateMachine) -> None:
        """IRQ handler for incoming byte on the GB link PIO."""

        if pio_mach.rx_fifo():
            self.rx_byte = pio_mach.get()
        else:
            print('no RX FIFO byte!')
            self.rx_ryte = 0
        
        # This delay forces the timing of sending TX bytes to the Game Boy
        # to drift one byte. Without it, the timing of bytes compared to when
        # the TX byte is sent to the PIO TX FIFO is inconsistent for some
        # titles (like the Game Boy Camera), causing the title to throw an 
        # error.
        utime.sleep_us(50)

        # by default, send 0 byte back
        self.tx_byte = 0x00

        if self.packet_state == STATE_IDLE:
            if self.rx_byte == 0x88:
                self.packet_state = STATE_MAGICBYTES_PARTIAL
            else:
                print('First magic byte bad!')

        elif self.packet_state == STATE_MAGICBYTES_PARTIAL:
            if self.rx_byte == 0x33:
                self.packet_state = STATE_HEADER
                self.remaining_bytes = 4
            else:
                print('Second magic byte bad!')
                self.packet_state = STATE_IDLE

        elif self.packet_state == STATE_HEADER:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 3:
                self.packet.command = self.rx_byte
            elif self.remaining_bytes == 2:
                self.packet.compression_flag = self.rx_byte
            elif self.remaining_bytes == 1:
                self.packet.data_length = self.rx_byte
            else:
                self.packet.data_length += self.rx_byte * 256
                if self.packet.data_length:
                    self.packet_state = STATE_PAYLOAD
                    self.remaining_bytes = self.packet.data_length
                else:
                    self.packet_state = STATE_CHECKSUM
                    self.remaining_bytes = 2
        
        elif self.packet_state == STATE_PAYLOAD:
            idx = self.packet.data_length - self.remaining_bytes
            self.remaining_bytes -= 1
            self.packet.data[idx] = self.rx_byte
            if self.remaining_bytes == 0:
                self.packet_state = STATE_CHECKSUM
                self.remaining_bytes = 2
        
        elif self.packet_state == STATE_CHECKSUM:
            self.remaining_bytes -= 1
            if self.remaining_bytes == 1:
                self.packet.checksum = self.rx_byte
                # This response byte will get queued after the next byte
                # which is already coming into the PIO due to the 50 us delay
                # above. It gets sent to the Game Boy alongside the first 
                # response byte.
                self.tx_byte = 0x81
            else:
                self.packet.checksum += self.rx_byte * 256
                self.packet_state = STATE_RESPONSE_READY
                # Similar thing here, this will get delayed by one byte then
                # sent to the Game Boy alongside the final response byte
                self.tx_byte = self.printer_status
 
        elif self.packet_state == STATE_RESPONSE_READY:
            self.packet_state = STATE_RESPONSE_PARTIAL
            # First response byte (0x81) was sent here

        elif self.packet_state == STATE_RESPONSE_PARTIAL:
            self.packet_state = STATE_IDLE
            self.complete_packet = True
            # Second response byte (printer status) was sent here

        self.pio_mach.put(self.tx_byte)
    
    def check_handle_packet(self) -> None:
        """Check if there's a complete packet and handle it.
        
        Each command does the following things:
        INIT - Initializes printer
        DATA - Copies data from GBPacket to the data buffer
        PRINT - Sets flag that print is ready and saves margin info. Starts
            off a counter to make the Game Boy think a print is actually
            occuring for a short time (actual printing is done after the link
            is complete and the Game Boy thinks it's done).
        BREAK - Same as INIT
        STATUS - Sends status info back to Game Boy. After a PRINT command,
            ticks down the fake printing counter, then sets status to a 
            completed print when the counter reaches zero.  
        """

        if not self.complete_packet:
            return
        
        self.leds.gb_activity.toggle()
     
        # print(
        #     f'Packet type: {self.packet.command}, '
        #     f'Printer status: {self.printer_status}, '
        #     f'Print ticks: {self.fake_print_ticks}, ' 
        #     f'Packet time: {utime.ticks_ms()}'
        # )

        if self.packet.command == COMMAND_INIT:
            self.initialize_emu_printer()

        elif self.packet.command == COMMAND_DATA:
            if self.packet.data_length == 0:
                print('Received stop data packet')
            else:
                pck = self.data_buffer.received_packets
                self.data_buffer.copy_new_packet(self.packet)
                cmp = bool(self.packet.compression_flag)
                self.data_buffer.gb_compression_flag[pck] = cmp
                self.printer_status = PRINTER_READY_TO_PRINT       

        elif self.packet.command == COMMAND_PRINT:
            if self.printer_status == PRINTER_READY_TO_PRINT:
                self.printer_status = PRINTER_PRINTING
                if (
                    self.packet.data[1] % 16 # there's a bottom margin
                    or self.data_buffer.check_buffer_ready_to_print()
                ):
                    self.lcd.queue_message('Real print ready!')
                    self.data_buffer.ready_to_convert.set()
                    self.fake_print_ticks = 5
                else:
                    self.lcd.queue_message('Fake printing...')
                    self.fake_printing = True
                    print('This is not the end of a print!')
                    self.fake_print_ticks = 10

        elif self.packet.command == COMMAND_BREAK:
            self.initialize_emu_printer()
            
        elif self.packet.command == COMMAND_STATUS:
            if self.printer_status == PRINTER_PRINTING:
                if (
                    self.fake_printing
                    or self.data_buffer.print_complete.check()
                ):
                    self.fake_print_ticks -= 1
                    if self.fake_print_ticks <= 0:
                        self.printer_status = PRINTER_COMPLETE
                        if self.fake_printing:
                            self.lcd.queue_message('Fake print done')
                        self.fake_printing = False
                        self.data_buffer.print_complete.clear()
            elif self.printer_status == PRINTER_COMPLETE:
                self.printer_status = PRINTER_IDLE
                    
        self.complete_packet = False
        self.last_packet_time = utime.ticks_ms()
