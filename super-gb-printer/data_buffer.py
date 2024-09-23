"""DataBuffer class

A DataBuffer contains buffers for GB tile data extracted from incoming 
GB packets, and graphics data to be sent to the the POS printer. It also 
includes methods for manipulating data between different buffers.
"""

import rp2
import typing
from micropython import const
from ulab import numpy as np

import lcd_i2c
import fake_lcd


# the important nubmers that set how big the buffers are
# most printable images are at most two screens tall, but what about all
# the giant banners you can make in Super Mario Bros. Deluxe?
NUM_GB_BUFFER_SCREENS = const(16)
NUM_POS_BUFFER_SCREENS = const(2)

# constants to work out the size of data buffers
PACKETS_PER_SCREEN = const(9)
PACKET_SIZE = const(640) # 0x280
NUM_PACKETS = NUM_GB_BUFFER_SCREENS * PACKETS_PER_SCREEN
GB_DATA_BUFFER_DIMS = (NUM_PACKETS, PACKET_SIZE)

SCREEN_WIDTH = const(160)
SCREEN_HEIGHT = const(144)
POS_PIXELS_PER_BYTE = const(8)
POS_BUFFER_DIMS = (
    SCREEN_HEIGHT * NUM_POS_BUFFER_SCREENS, 
    SCREEN_WIDTH // POS_PIXELS_PER_BYTE
)

BIG_ROWS_PER_PACKET = const(2)
TILES_PER_BIG_ROW = const(20)
BYTES_PER_ROW = const(2)
ROWS_PER_TILE = const(8)
BYTES_PER_TILE = ROWS_PER_TILE * BYTES_PER_ROW
BYTES_PER_BIG_ROW = TILES_PER_BIG_ROW * BYTES_PER_TILE


class GBPacket():
    """Contains data for one GB printer packet.
    
    Used by the DataBuffer class to hold incoming packet data from the 
    Game Boy software.
    """

    def __init__(self):
        self.command = 0
        self.compression_flag = 0
        self.data_length = 0
        self.data = bytearray(PACKET_SIZE)
        self.checksum = 0
        self.calc_checksum = 0


class DataBuffer():
    """
    A DataBuffer contains buffers for GB tile data extracted from incoming 
    GB packets, and graphics data to be sent to the the POS printer. It also 
    includes methods for manipulating data between different buffers.
    """

    AnyLCD = typing.Union[lcd_i2c.LCD, fake_lcd.FakeLCD, None]
    
    def __init__(self, lcd: AnyLCD = None) -> None:
        """Instantiate the class.
        
        Args:
            lcd: LCD instance for an optional attached LCD screen
        """

        self.lcd = lcd if lcd else fake_lcd.FakeLCD()

        self.gb_buffer = np.zeros(GB_DATA_BUFFER_DIMS, dtype=np.uint8)
        self.decomp_buffer = np.zeros(PACKET_SIZE, dtype=np.uint8)
        self.num_converted_packets = 0
        self.num_packets = 0
        self.current_page = 0
        self.gb_compression_flag = [False] * NUM_PACKETS
        self.data_length = [0] * NUM_PACKETS
        self.pos_buffer = [
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
        ]

        self.dma = rp2.DMA()
        self.dma_ctrl = self.dma.pack_ctrl()
    
    def clear_packets(self) -> None:
        """Reset GB packets to prepare for next print."""

        self.num_packets = 0
        self.current_page = 0
        self.gb_compression_flag = [False] * NUM_PACKETS
        self.data_length = [0] * NUM_PACKETS
    
    def copy_new_packet(self, packet: GBPacket) -> None:
        """Copies needed data from GBPacket to the proper buffers.
        
        Grabs the compressions flag, data length (for compressed packets)
        and the data itself.

        Args:
            packet: The incoming GBPacket 
        """

        if self.num_packets == GB_DATA_BUFFER_DIMS:
            raise ValueError('GB packet buffer is full!')
        self.dma_copy_packet(packet.data, self.num_packets)
        self.gb_compression_flag[self.num_packets] = bool(packet.compression_flag)
        self.data_length[self.num_packets] = packet.data_length
        self.num_packets += 1
        print(f"Received new packet, I have {self.num_packets}")
    
    def dma_copy_packet(self, packet: bytearray, idx: int) -> None:
        """Copy data packet data to GB buffer using DMA.

        Args:
            packet: The bytearray from a GBPacket
            idx: the index in the GB tile buffer where incoming data will go
        """

        self.dma.config(
            read = packet,
            write = self.gb_buffer[idx,:],
            count = len(packet) // 4,
            ctrl = self.dma_ctrl,
            trigger = True
        )
        
    def convert_page_of_packets(self, page: int) -> None:
        """Converts one page (18 packets) of data.
        
        Args:
            page: Naturally, the page to convert
        """

        self.current_page = page + 1
        p_low = page*18
        p_hi = min((page+1)*18, self.num_packets)
        self.convert_packet_range(p_low, p_hi)
        
    def convert_packet_range(self, start: int, end: int) -> None:
        """Converts a range of packets from GB tile to POS graphics format.
        
        Used by the above methods that specify what that range is.

        Args:
            start: 
                Starting packet in the GB tile buffer
            end: 
                Ending packet in the GB tile filter plus one, thanks to 
                Python indexing 
        """

        self.lcd.clear()
        self.lcd.print("Converting")
        if self.num_pages > 1:
            self.lcd.set_cursor(0, 1)
            self.lcd.print(f"Page {self.current_page}/{self.num_pages}")
        for pos_idx, gb_idx in enumerate(range(start, end)):
            self.lcd.set_cursor(11, 0)
            self.lcd.print(f"{gb_idx}")
            self.convert_one_packet(gb_idx, pos_idx)
        self.num_converted_packets = end - start
    
    def convert_one_packet(self, gb_idx: int, pos_idx: int = -1) -> None:
        """Converts one packet from GB tile to POS graphics format.

        Args:
            gb_idx: 
                Index of packet in the GB tile buffer to be converted
            pos_idx: 
                Index of data in the POS graphics data buffer. May be 
                different than gb_idx since the buffers are different sizes
                and data is generally converted one page at a time.
        """

        if self.gb_compression_flag[gb_idx]:
            self.decompress_packet_in_buffer(gb_idx)
        if pos_idx == -1:
            pos_idx = gb_idx

        # big row is a row of GB tiles
        for big_row in range(BIG_ROWS_PER_PACKET):
            for tile_idx in range(TILES_PER_BIG_ROW):
                tile_offset = (
                    big_row * BYTES_PER_BIG_ROW
                    + tile_idx * BYTES_PER_TILE
                )

                # each row is two bytes, little endian
                lbytes = self.gb_buffer[
                    gb_idx, tile_offset : tile_offset+BYTES_PER_TILE : 2
                ]
                hbytes = self.gb_buffer[
                    gb_idx, tile_offset+1:tile_offset+BYTES_PER_TILE+1:2
                ]

                # white doesn't need to be tracked since it's not printed
                # white        = ~lbytes & ~hbytes
                lightgray_tile =  lbytes & ~hbytes
                darkgray_tile  = ~lbytes &  hbytes
                black_tile     =  lbytes &  hbytes
                
                tone49_tile = black_tile | darkgray_tile 
                tone50_tile = black_tile | lightgray_tile 
                tone51_tile = black_tile | lightgray_tile 
                tone52_tile = black_tile | darkgray_tile | lightgray_tile 

                trow = (pos_idx * 2 + big_row) * ROWS_PER_TILE

                self.pos_buffer[0][trow:trow+8, tile_idx] = tone49_tile
                self.pos_buffer[1][trow:trow+8, tile_idx] = tone50_tile
                self.pos_buffer[2][trow:trow+8, tile_idx] = tone51_tile
                self.pos_buffer[3][trow:trow+8, tile_idx] = tone52_tile
    
    def decompress_packet_in_buffer(self, packet_idx: int) -> None:
        """Decompresses a packet and copies results back to GB tile buffer.
        
        Args:
            packet_idx: Index of packet to be decompressed
        """
        dl = self.data_length[packet_idx]
        self.decompress_packet_data(self.gb_buffer[packet_idx,:], dl)
        self.gb_buffer[packet_idx,:] = self.decomp_buffer
    
    def decompress_packet_data(
            self, comp_packet: np.ndarray, data_length: int
        ) -> None:
        """The decompression algorithm.
        
        Args:
            comp_packet: The data to be decompressed
            data_length: 
                The length of the data to be decompressed. Needed since the 
                incoming data is probably a full size packet (0x280 bytes)
                but the actual comrpessed data is smaller than that.
        """
        comp_idx = 0
        decomp_idx = 0
        while comp_idx < data_length:
            comp_byte = comp_packet[comp_idx]
            # MSB determines if the next section of data is compressed
            # MSB = 1, data is compressed (one byte repeated)
            if comp_byte & 0x80:
                run = 2 + comp_byte - 0x80
                repeat_byte = comp_packet[comp_idx+1]
                self.decomp_buffer[decomp_idx:decomp_idx+run] = repeat_byte
                comp_idx += 2
                decomp_idx += run
            # MSB = 0, data is not compressed
            else:
                run = 1 + comp_byte
                self.decomp_buffer[decomp_idx:decomp_idx+run] = \
                    comp_packet[comp_idx+1:comp_idx+run+1]
                comp_idx += run + 1
                decomp_idx += run
    
    @property
    def num_pages(self):
        """Get the number of pages (18 packets) received."""
        return ((self.num_packets - 1) // 18) + 1
    

