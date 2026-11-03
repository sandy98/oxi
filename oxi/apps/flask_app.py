#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, threading, importlib
from pathlib import Path

currfile = Path(__file__)
currdir = currfile.parent
appspath = currdir.parent
oxipath = appspath.parent
sys.path.insert(0, str(appspath))
sys.path.insert(0, str(oxipath))

from oxi.server import run # type: ignore
sep = os.path.sep
venvstr=f".examples-virtual-env{sep}lib{sep}python3.10{sep}site-packages{sep}"
venvpath = Path(f"{str(appspath)}/{venvstr}") 
sys.path.insert(0, str(venvpath))

from flask import Flask, jsonify, request #, __version__ as flask_version  # type: ignore

flask_version = importlib.metadata.version("flask")

# Inicializamos la aplicación WSGI oficial de Flask
app = Flask(__name__)

current_thread = threading.current_thread()
thread_name = current_thread.name

@app.route("/asyn_flask")
async def asyyn_flask():
    return "<h1>Look Ma! Async Flask!!</h1>"

@app.route("/")
def flask_root():
    return (
        f'<h1>Hello World from Flask v.<span style="color: #008800;">({flask_version})</span> running natively inside Julia-OxiServer!</h1>\n'
        f"<p>This is standard WSGI routing translated to ASGI on Thread {thread_name}.</p>"
        """<p>
        <form action="/flask_json" method="get">
        <label>Want a taste of json?</label>
        &nbsp;
        <input type=text name=user required value="Clark Kent"/>
        <input type="submit" value="Submit" />
        </form>
        </p>
        <p><a href="/asyn_flask">Is there something like async Flask??</a></p>
        """
    )

@app.route("/flask_json")
def flask_json():
    # Extraemos un parámetro de la Query String usando la API nativa de Flask
    user_param = request.args.get("user", "Guest")
    
    # Devuelve una respuesta JSON estructurada real
    return jsonify({
        "status": "success",
        "framework": "Flask 3.x",
        "bridge_type": "wsgi2asgi (Ernesto's Specification)",
        "hello_target": user_param,
        "multiple_dispatch": "Active"
    })


if __name__ == "__main__":
    # asyncio.run(run_dev_server(app, host="0.0.0.0", port=8086))
    from oxi.server import run # type: ignore
    run(app, '0.0.0.0', 8086)
