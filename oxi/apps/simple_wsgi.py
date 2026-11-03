#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, asyncio

from pathlib import Path

currfile = Path(__file__)
currdir = currfile.parent
appspath = currdir.parent
oxipath = appspath.parent
sys.path.insert(0, str(appspath))
sys.path.insert(0, str(oxipath))

from oxi.server import run
from oxi.utils import encode_image

visitors = 0

# async def application(environ, start_response): # This works under OxiServer, but fails with Gunicorn
def application(environ, start_response):
    """
    Ernesto's barebones WSGI Hello World.
    Validates the standard PEP 3333 environment and lifecycle.
    """
    global visitors

    # Read variables directly from the injected Linux environment map
    method = environ.get("REQUEST_METHOD", "UNKNOWN")
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    
    encoded_img = ""

    image_path = "static/img/fine_old_wsgi.jpeg"
    with open(image_path, "rb") as fp:
        image = fp.read()
    encoded_img = encode_image(image, "image/jpeg")

    visitors += 1


    output = ""
    output += """
    <style>
        body {
            font-size: 1.2rem;
            font-family: Arial, Helvetica, sans-serif;
        }
    </style>
    """
    output += f"<h2 style='text-align: center; color:#008800;'>Hello World from pure WSGI running inside Julia-OxiServer!</h2>\n"
    output += f"<p><strong>Method:</strong> {method}</p>"
    output += f"<p><strong>Path:</strong> {path}</p>"
    output += f"<p><strong>Query String received:</strong> {query}</p>"
    output += f"<p><strong>You're visitor number:</strong> {visitors}</p>"
    output += f'''<p style="text-align: center;">
        <img style="max-width: 960px; border-radius: 10px;" src={encoded_img} />
    </p>
    '''
    
    encoded = output.encode("latin-1") 

    status = "200 OK"
    response_headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", f"{len(encoded)}"),
        ("X-Powered-By", "OxiServer WSGI Bridge")
    ]
    
    # Trigger the standard start_response callback provided by Julia's bridge
    start_response(status, response_headers)
    
    return [encoded]
    # return [output]    

if __name__ == "__main__":
    # asyncio.run(run_dev_server(application, host="0.0.0.0", port=8086))
    from oxi.server import run
    run(application, '0.0.0.0', 8086)
