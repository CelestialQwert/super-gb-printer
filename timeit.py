import utime

def timeit(f, *args, **kwargs):
    def new_func(*args, **kwargs):
        t = utime.ticks_us()
        result = f(*args, **kwargs)
        micros = utime.ticks_diff(utime.ticks_us(), t)
        print(f'{f.__name__} execution time: {micros} us')
        return result
    return new_func