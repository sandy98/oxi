#-*- coding: utf-8 -*-
import re, asyncio, platform, threading, sys, termios
from functools import wraps
from contextlib import contextmanager
from http import HTTPStatus

######################################################################################

http_status_dict = {h.value: h.phrase for h in HTTPStatus}

######################################################################################

def is_windows():
    """
    Check if the current operating system is Windows.
    """
    return platform.system() == 'Windows'

def is_linux():
    """
    Check if the current operating system is Linux.
    """
    return platform.system() == 'Linux'

def is_mac():
    """
    Check if the current operating system is macOS.
    """
    return platform.system() == 'Darwin'
def is_unix():
    """
    Check if the current operating system is Unix-like.
    """
    return platform.system() in ['Linux', 'Darwin']

def is_posix():
    """
    Check if the current operating system is POSIX-compliant.
    """
    return os.name == 'posix'

def is_nt():
    """
    Check if the current operating system is Windows NT.
    """
    return os.name == 'nt'


######################################################################################

def to_bytes(text, encoding='utf-8'): 
    if type(text) == bytes:
        return text
    elif type(text) == int or type(text) == float:
        return str(text).encode(encoding)
    elif isinstance(text, (tuple, list)):
        return list(map(to_bytes, text))
    else:
        return str(text).encode(encoding)

######################################################################################

def safe_filename(name):
    name = name.replace(' ', '_')
    return re.sub(r'[^a-zA-Z0-9._-]', '', name)

######################################################################################

def dual_mode(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                async def async_wrapper():
                    return await asyncio.to_thread(func, *args, **kwargs)
                return async_wrapper()
        except RuntimeError:
            pass
        return func(*args, **kwargs)
    
    return wrapper

######################################################################################

async def aopen(filename:str, mode:str='r'):
    coro = asyncio.to_thread(open, filename, mode)
    return await coro

######################################################################################

@contextmanager
def no_ctrlc_echo():
    """
    Context manager to suppress ^C echo in terminal when Ctrl+C is pressed.
    Only works on POSIX terminals (Linux, macOS).
    """
    if not sys.stdin.isatty():
        yield
        return

    fd = sys.stdin.fileno()
    try:
        attrs = termios.tcgetattr(fd)
        new_attrs = attrs[:]
        new_attrs[3] = new_attrs[3] & ~termios.ECHOCTL  # Clear ECHOCTL
        termios.tcsetattr(fd, termios.TCSANOW, new_attrs)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

######################################################################################

class ResultThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.result = None
        super().__init__(*args, **kwargs)

    def run(self):
        self.result = self._target(*self._args, **self._kwargs)

######################################################################################

class SmartDict(dict):
    """SmartDict class with attributes equating dict keys"""

    def __init__(self, d: dict = None, **kw):
        super().__init__(d or {}, **kw)

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        raise AttributeError(f"'SmartDict' object has no attribute '{attr}'")

    def __setattr__(self, attr, value):
        if hasattr(dict, attr):
            raise AttributeError(f"Cannot set attribute '{attr}': reserved name")
        self[attr] = value

    def __delattr__(self, attr):
        if attr in self:
            del self[attr]
        else:
            raise AttributeError(f"'SmartDict' object has no attribute '{attr}'")

    def copy(self):
        return SmartDict(super().copy())

######################################################################################

