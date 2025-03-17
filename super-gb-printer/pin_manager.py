"""Classes for handling auxillary things attached to pins on the Pico."""

from machine import Pin
import pinout as pinn


class DIPManager():
    """Class DIPManager

    Handles reading of DIP switches and the settings they control.
    """

    def __init__(self):
        """Instantiate the class."""

        last_dip_switch = pinn.FIRST_DIP_SWITCH + pinn.NUM_DIP_SWITCHES
        self.dip_switches = [
            Pin(x, Pin.IN, Pin.PULL_DOWN) 
            for x in range(pinn.FIRST_DIP_SWITCH, last_dip_switch)
        ]

    @property
    def scale_2x(self):
        """Sets whether the print is scaled by 2x.
        
        Overrides the no scale setting when enabled.
        """
        return self.dip_switches[0].value()
    
    @property
    def no_scale(self):
        """Sets whether the print is not scaled."""
        return self.dip_switches[1].value()
    
    @property
    def add_bottom_margin(self):
        """Sets whether a bottom margin is added.
        
        When enabled, a bottom margin is added that makes centers the image
        vertically on the paper.
        """
        return self.dip_switches[2].value()
    
    @property
    def cut_mode(self):
        """Sets whether the print is automatically cut.
        
        Disable it when printing custom banners, such as with Donkey Kong
        Country (which isn't working right now).

        *****Currently unused*****
        
        """
        return self.dip_switches[3].value()

class ButtonManager():
    """Class ButtonManager

    Handles reading of buttons.
    """
    def __init__(self):
        last_button = pinn.FIRST_BUTTON + pinn.NUM_BUTTONS
        self.buttons = [
            Pin(x, Pin.IN, Pin.PULL_DOWN) 
            for x in range(pinn.FIRST_BUTTON, last_button)
        ]


class LEDManager():
    """Class LEDManager

    Contains all the LEDs and gives them descriptive names.
    """
    def __init__(self):
        self.pio_enabled = Pin(pinn.GB_PIO_ENABLED, Pin.OUT)
        self.gb_activity = Pin(pinn.GB_LED_ACTIVITY, Pin.OUT)
        self.pos_activity = Pin(pinn.POS_TX_ACTIVITY, Pin.OUT)
        self.leds = [self.pio_enabled, self.gb_activity, self.pos_activity]

    def all_off(self) -> None:
        """Turn all the LEDs off."""

        for led in self.leds:
            led.off()
        self.gb_activity.off()


if __name__ == "__main__":
    import utime
    settings = DIPManager()
    btn = ButtonManager()
    while True:
        dips = [x.value() for x in settings.dip_switches]
        btns = [x.value() for x in btn.buttons]
        print(f"DIPs: {dips}, Buttons: {btns}")
        utime.sleep(1)
