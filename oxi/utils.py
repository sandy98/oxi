#-*- coding: utf-8 -*-
import re, asyncio
from functools import wraps


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

