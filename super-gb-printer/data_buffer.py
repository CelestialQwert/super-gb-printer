import rp2
from micropython import const
from ulab import numpy as np

import fake_lcd

NUM_GB_BUFFER_SCREENS = const(16)
NUM_POS_BUFFER_SCREENS = const(2)

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

class DataBuffer():
    def __init__(self, lcd=None):

        self.lcd = lcd if lcd else fake_lcd.FakeLCD()

        self.gb_buffer = np.zeros(GB_DATA_BUFFER_DIMS, dtype=np.uint8)
        self.num_converted_packets = 0
        self.num_packets = 0
        self.current_page = 0
        self.gb_compression_flag = [False] * NUM_PACKETS
        self.pos_buffer = [
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
            np.zeros(POS_BUFFER_DIMS, dtype=np.uint8),
        ]

        self.dma = rp2.DMA()
        self.dma_ctrl = self.dma.pack_ctrl()
    
    def clear_packets(self):
        self.num_packets = 0
        self.current_page = 0
        self.gb_compression_flag = [False] * NUM_PACKETS
    
    def dma_copy_new_packet(self, packet):
        if self.num_packets == GB_DATA_BUFFER_DIMS:
            raise ValueError('GB packet buffer is full!')
        self.dma_copy_packet(packet, self.num_packets)
        self.num_packets += 1
        print(f"Received new packet, I have {self.num_packets}")
    
    def dma_copy_packet(self, packet, idx):
        self.dma.config(
            read = packet,
            write = self.gb_buffer[idx,:],
            count = len(packet) // 4,
            ctrl = self.dma_ctrl,
            trigger = True
        )
    
    def convert_all_packets(self):
        num_packs = min(18, self.num_packets)
        self.convert_packet_range(0, num_packs)
    
    def convert_page_of_packets(self, page):
        self.current_page = page + 1
        p_low = page*18
        p_hi = min((page+1)*18, self.num_packets)
        self.convert_packet_range(p_low, p_hi)
        
    def convert_packet_range(self, start, end):
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
    
    def convert_one_packet(self, gb_idx, pos_idx=-1):
        if pos_idx == -1:
            pos_idx = gb_idx

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
    
    def decrypt_packet(self, packet_idx):
        raise NotImplementedError

    @property
    def num_pages(self):
        return ((self.num_packets - 1) // 18) + 1
    

