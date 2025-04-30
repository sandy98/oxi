# -*- coding: utf-8 -*-
from activate_this import oxi_env

if oxi_env:
    from oxi import __version__ as oxi_version
from oxi.tests.first import first
from oxi.tests.second import second

response = first + second

print(f"OXI version: {oxi_version} sends unviersal response: {response}")

