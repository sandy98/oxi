#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
from pathlib import Path
from typing import Callable, Any

currfile = Path(__file__)
currdir = currfile.parent
appspath = currdir.parent
oxipath = appspath.parent
sys.path.insert(0, str(appspath))
sys.path.insert(0, str(oxipath))

from oxi.server import run
sep = os.path.sep
venvstr=f".examples-virtual-env{sep}lib{sep}python3.10{sep}site-packages{sep}"
venvpath = Path(f"{str(appspath)}/{venvstr}") 
sys.path.insert(0, str(venvpath))

class SimpleASGIApp:
    """
    A simple ASGI application that returns a "Hello, World!" response.
    """
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = [(b'content-type', b'text/plain')]
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': headers
            })
            await send({
                'type': 'http.response.body',
                'body': b'Hello, World! This is a simple ASGI app. Replacing FastAPI for testing purposes.',
            })
    
fastapi_available = False
app = SimpleASGIApp()

try:
    from fastapi import FastAPI  # pyright: ignore[reportMissingImports] 
    fastapi_available = True
except ImportError:
    fastapi_available = False

if fastapi_available:
    # Inicializamos la aplicación ASGI principal
    app = FastAPI(title="Julia ASGI Server Boot")  # pyright: ignore[reportPossiblyUnboundVariable]

    @app.get("/")
    def read_root():
        return {
            "status": "success",
            "message": "Hello World from FastAPI running natively inside Julia... or maybe Python...!",
            "engine": "Julia ASGI Core (Single-Threaded)"
        }

    @app.get("/items/{item_id}")
    def read_item(item_id: int, q: str|None = None):
        # FastAPI parseará el path dinámico y la query string automáticamente
        return {
            "item_id": item_id, 
            "query_param": q,
            "context": "Multiple Dispatch Rulez!"
        }
    
if __name__ == "__main__":
    # asyncio.run(run_dev_server(app, host="0.0.0.0", port=8086))
    from oxi.server import run
    run(app, '0.0.0.0', 8086)
