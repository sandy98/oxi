
if __name__ == "__main__" and not __package__:
    __package__ = "oxi"

from .__about__ import __version__, __config__
from . import server, static, app, utils, tina, apps

__all__ = [
    "__version__", 
    "__config__", 
    "tina", 
    "server", 
    "static", 
    "app", 
    "utils", 
    "apps"
]

# print(f"This is all Oxi has to offer: {__all__}")
