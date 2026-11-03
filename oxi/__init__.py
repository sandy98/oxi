# -*- coding: utf-8 -*-

if __name__ == "__main__" and not __package__:
    __package__ = "oxi"

from .__about__ import __version__, __config__
from . import server, static, app, utils, tina, apps

__author__ = "Domingo E. Savoretti"
__email__ = "esavoretti@gmail.com"
__license__ = "MIT"
__url__ = "https://github.com/sandy98/oxi"
__description__ = "ASGI full stack: Web Server, Web App and a ton of goodies."
__copyright__ = "Copyright (c) 2025 Domingo E. Savoretti"
__oxi_port__ = 8086
__oxi_host__ = "0.0.0.0"

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
