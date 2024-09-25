"""Pin definitions for all atached devices."""

from micropython import const

#GB_CLK MUST BE SET MANUALLY IN gb_link.py
GB_CLK = const(2)
GB_IN = const(4)
GB_OUT = const(5)
GB_LED_ACTIVITY = const(7)
GB_PIO_ENABLED = const(6)

POS_UART = const(0)
POS_TX = const(16)
POS_RX = const(17)
POS_TX_ACTIVITY = const(8)

LCD_I2C = const(1)
LCD_SDA = const(26)
LCD_SCL = const(27)

BUTTON1 = const(10)
DIP1 = const(11)
DIP2 = const(12)
DIP3 = const(13)
DIP4 = const(14)
DIP5 = const(15)
