import rp2
from collections import namedtuple
from micropython import const
from ulab import numpy as np

import fake_lcd

NUM_SCREENS = const(5)

PACKETS_PER_SCREEN = const(9)
PACKET_SIZE = const(640) # 0x280
NUM_PACKETS = NUM_SCREENS * PACKETS_PER_SCREEN
GB_DATA_BUFFER_DIMS = (NUM_PACKETS, PACKET_SIZE)

SCREEN_WIDTH = const(160)
SCREEN_HEIGHT = const(144)
POS_PIXELS_PER_BYTE = const(8)
POS_BUFFER_DIMS = (
    SCREEN_HEIGHT * NUM_SCREENS, 
    SCREEN_WIDTH // POS_PIXELS_PER_BYTE
)

BIG_ROWS_PER_PACKET = const(2)
TILES_PER_BIG_ROW = const(20)
BYTES_PER_ROW = const(2)
ROWS_PER_TILE = const(8)
BYTES_PER_TILE = ROWS_PER_TILE * BYTES_PER_ROW
BYTES_PER_BIG_ROW = TILES_PER_BIG_ROW * BYTES_PER_TILE


ToneImageBuffer = namedtuple(
    'ToneImageBuffer',
    ['tone49', 'tone50', 'tone51', 'tone52']
)

class DataBuffer():
    def __init__(self, lcd=None):

        self.lcd = lcd if lcd else fake_lcd.FakeLCD()

        self.gb_buffer = np.zeros(GB_DATA_BUFFER_DIMS, dtype=np.uint8)
        self.clear_packets()
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
        self.lcd.clear()
        self.lcd.print('Converting')
        for packet_idx in range(self.num_packets):
            print(f"Converting packet {packet_idx:02}/{self.num_packets:02}")
            self.convert_one_packet(packet_idx)
    
    def convert_one_packet(self, packet_idx):
        for big_row in range(BIG_ROWS_PER_PACKET):
            for tile_idx in range(TILES_PER_BIG_ROW):
                tile_offset = (
                    big_row * BYTES_PER_BIG_ROW
                    + tile_idx * BYTES_PER_TILE
                )

                # each row is two bytes, little endian
                lbytes = self.gb_buffer[
                    packet_idx, tile_offset : tile_offset+BYTES_PER_TILE : 2
                ]
                hbytes = self.gb_buffer[
                    packet_idx, tile_offset+1:tile_offset+BYTES_PER_TILE+1:2
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

                trow = (packet_idx * 2 + big_row) * ROWS_PER_TILE

                self.pos_buffer[0][trow:trow+8, tile_idx] = tone49_tile
                self.pos_buffer[1][trow:trow+8, tile_idx] = tone50_tile
                self.pos_buffer[2][trow:trow+8, tile_idx] = tone51_tile
                self.pos_buffer[3][trow:trow+8, tile_idx] = tone52_tile
    
    def decrypt_packet(self, packet_idx):
        raise NotImplementedError
    

