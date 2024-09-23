"""Contains a helper function for timing."""

import utime

def timeit(f, *args, **kwargs):
    def new_func(*args, **kwargs):
        t = utime.ticks_ms()
        result = f(*args, **kwargs)
        micros = utime.ticks_diff(utime.ticks_ms(), t)
        print(f'{f.__name__} execution time: {micros} ms')
        return result
    return new_func