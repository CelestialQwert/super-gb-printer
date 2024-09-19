
class FakeLCD():
    """Fake LCD class for when the screen isn't available."""
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