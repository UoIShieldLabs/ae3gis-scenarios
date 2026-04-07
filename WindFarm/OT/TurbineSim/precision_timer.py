import ctypes
import time

# Load libc
libc = ctypes.CDLL("libc.so.6")

# Define timespec struct for nanosleep
class Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long),
               ("tv_nsec", ctypes.c_long)]

def usleep(microseconds):
    """Sleeps for a specific number of microseconds."""
    # 1 microsecond = 1000 nanoseconds
    time_struct = Timespec(0, microseconds*1000)
    # 0 = CLOCK_REALTIME, 1 = CLOCK_MONOTONIC
    # Using 1 for better precision (monotonic)
    libc.clock_nanosleep(1, 0, ctypes.byref(time_struct), None)