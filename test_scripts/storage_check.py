import os

stat = os.statvfs("/")
size = stat[1] * stat[2]
free = stat[0] * stat[3]
used = size - free

KB = 1024
MB = 1024 * 1024

print(f"Size : {size:,} bytes, {size / KB:,} KB, {size / MB} MB")
print(f"Used : {used:,} bytes, {used / KB:,} KB, {used / MB} MB")
print(f"Free : {free:,} bytes, {free / KB:,} KB, {free / MB} MB")

if   size > 8 * MB : board, flash = "Unknown", 16 * MB
elif size > 4 * MB : board, flash = "Unknown",  8 * MB
elif size > 2 * MB : board, flash = "Unknown",  4 * MB
elif size > 1 * MB : board, flash = "Pico",     2 * MB
else               : board, flash = "Pico W",   2 * MB
print("{} board with {} MB Flash".format(board, flash // MB))