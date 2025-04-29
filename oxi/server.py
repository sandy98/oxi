# -*- coding: utf-8 -*-

import asyncio, os

from . import  __version__ as oxi_version
from .utils import dual_mode

async def is_static(resource:str) -> bool:
    """
    Check if the resource exists in the file system.
    """
    return await asyncio.to_thread(os.path.exists, resource)

async def is_file(resource:str) -> bool:
    """
    Check if the resource is a regular file.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    return exists and await asyncio.to_thread(os.path.isfile, resource)

async def is_dir(resource:str) -> bool:
    """
    Check if the resource is a directory.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    return exists and await asyncio.to_thread(os.path.isdir, resource)

async def is_exe(resource:str) -> bool:
    """
    Check if the resource is an executable file.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    return exists and await asyncio.to_thread(os.access, resource, os.X_OK)

async def is_cgi_exe(resource:str, cgi_dir:str="cig-bin") -> bool:
    """
    Check if the resource is a CGI executable.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    if not exists:
        return False
    is_exe = await is_exe(resource)
    if not is_exe:
        return False
    if not cgi_dir in resource:
        return False
    return True



class OxiProtocol: ...


