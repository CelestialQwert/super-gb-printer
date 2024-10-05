"""Class PinManager

Handles reading of DIP switches and buttons and the settings they control.
"""

from machine import Pin

import utimeit
import pinout as pinn


class PinManager():
    """Class PinManager

    Handles reading of DIP switches and buttons and the settings they control.
    """

    def __init__(self):
        """Instantiate the class."""

        last_button = pinn.FIRST_BUTTON + pinn.NUM_BUTTONS
        self.buttons = [
            Pin(x, Pin.IN, Pin.PULL_DOWN) 
            for x in range(pinn.FIRST_BUTTON, last_button)
        ]

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
        Country.
        """
        return self.dip_switches[3].value()
        


if __name__ == "__main__":
    import utime
    mgr = PinManager()
    while True:
        dips = [x.value() for x in mgr.dip_switches]
        btns = [x.value() for x in mgr.buttons]
        print(f"DIPs: {dips}, Buttons: {btns}")
        utime.sleep(1)
