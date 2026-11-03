#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from time import strftime

currfile = Path(__file__)
currdir = currfile.parent
appspath = currdir.parent
oxipath = appspath.parent
sys.path.insert(0, str(appspath))
sys.path.insert(0, str(oxipath))

# from oxi.server import run

visits = 0
gstate = {}

async def app(scope, receive, send):
    global gstate
    global visits
    visits += 1

# Garbage
    # if scope['type'] == 'lifespan':
    #     request_event = await receive()
    #     if request_event.get('type', '') == "lifespan.startup":
    #         print("\nI'll try to fool lifespan protocol by sending garbage... :-))\n")
    #         await send({'type': "morcilla"})
    #     return

# Failure
    # if scope['type'] == 'lifespan':
    #     request_event = await receive()
    #     if request_event.get('type') == "lifespan.startup":
    #         await send({'type': "lifespan.startup.failed", "message": "Morcilla was too spicy!"})
    #     return

# Success
    if scope['type'] == 'lifespan':
        gstate = scope.get('state', {})
        while True:
            request_event = await receive()
            if request_event.get('type') == "lifespan.startup":
                gstate['start_time'] = strftime("%H:%M:%S")
                await send({'type': "lifespan.startup.complete"})
            request_event = await receive()
            if request_event.get('type') == "lifespan.shutdown":
                print(f"The mockingbird flew away at {strftime('%H:%M:%S')} ...")
                await send({'type': "lifespan.shutdown.complete"})
                break
    
    # 1. Send the ASGI response start event (Headers)
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [(b'content-type', b'text/html; charset=utf-8')],
    })
    
    # 2. Send the ASGI response body event
    await send({
        'type': 'http.response.body',
        'body': f'''
        <html>
            <head>
                <title>My ASGI App</title>
                <style>
                    body {{
                        font-family: Arial, Helvetica, sans-serif;
                    }}
                    h1 {{
                        color: steelblue;
                        text-align: center;
                        padding: 20px;
                        border: solid 1px steelblue;
                        border-radius: 10px;
                        margin: 2rem 10%;
                        width: 80%;
                    }}
                    p {{
                        font-size: 1.5rem;
                    }}
                </style>
            </head>
            <body>
                <h1>Hello from a Python ASGI app running inside a Julia Server!</h1>
                <p>&nbsp;</p>
                <p><strong>Visits:</strong> {visits}</p>
                <p><strong>App start time: </strong> {gstate.get('start_time')}</p>
                <p><strong>Current time: </strong> {strftime("%H:%M:%S")}</p>
                <p><strong>Server: </strong> {gstate.get('server', "Unknown")}</p>
            </body>
        </html>
        '''.encode('utf-8'),
        'more_body': False
    })


# if __name__ == "__main__":
#     # asyncio.run(run_dev_server(app, host="0.0.0", port=8086))
#     from oxi.server import run
#     run(app, '0.0.0.0', 8086)
