import time
from contextlib import contextmanager
import sys, termios

@contextmanager
def no_ctrlc_echo():
    if not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    try:
        modified = original[:]
        modified[3] &= ~termios.ECHOCTL
        termios.tcsetattr(fd, termios.TCSANOW, modified)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, original)

if __name__ == "__main__":
    try:
        with no_ctrlc_echo():
            print("Running. Press Ctrl+C to test.")
            time.sleep(30)
    except KeyboardInterrupt:
        print("Got KeyboardInterrupt.")


