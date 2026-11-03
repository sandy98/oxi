#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
from pathlib import Path

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

from fastapi import FastAPI

# Inicializamos la aplicación ASGI principal
app = FastAPI(title="Julia ASGI Server Boot")

@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "Hello World from FastAPI running natively inside Julia... or maybe Python...!",
        "engine": "Julia ASGI Core (Single-Threaded)"
    }

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
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
