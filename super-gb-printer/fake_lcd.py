
class FakeLCD():
    """Fake LCD class for when the screen isn't available.
    
    Most methods do nothing, but the print method redirects to stdout.
    """
    def __init__(self):
        pass

    def begin(self):
        pass

    def clear(self):
        pass

    def print(self, text: str):
        print(f"To LCD: {text}")

    def set_cursor(self, *args, **kwargs):
        pass

    def create_char(self, *args, **kwargs):
        pass