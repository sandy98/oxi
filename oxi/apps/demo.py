#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# pyright: reportMissingImports=false

import asyncio, sys, os, threading, multiprocessing, random
from datetime import datetime
from mimetypes import types_map
from pathlib import Path
from http import HTTPStatus

types_map[".md"] = "text/markdown"
sep = os.path.sep

filepath = Path(__file__)
# print(str(filepath))
parentpath = filepath.parent
# print(str(parentpath))
grandparentpath = parentpath.parent
# print(str(grandparentpath))
sys.path.insert(0, str(parentpath))
sys.path.insert(0, str(grandparentpath))

from tina.websocket import WebSocket, CONNECTED
from utils import encode_image, to_bytes, bytes_to_human_readable
from app import OxiApp

from static import static_app # type: ignore
from server import run
from apps.simple_wsgi import application as wsgi_app
from apps.flask_app import app as flask_app
from apps.simple_asgi import app as simple_asgi_app
from apps.fast_app import app as fast_app

app = OxiApp("Oxi Demo App")
app.next = static_app

visitors = 0
@app.get("/raise")
@app.get("/raise/<code:int>")
async def raise_error(code=500):
    from http import HTTPStatus
    phrase = ""
    try:
        phrase = HTTPStatus(code).phrase
    except Exception as exc:
        phrase = str(exc)

    msg = app.form.get("err_msg", 'Something horrible happened!')
    await app.error(code, phrase=phrase, scope=app.scope, send=app.send, msg=msg, _=None)

@app.get("/home")
async def index():
    global visitors
    visitors += 1
    form = app.form
    formstr = "<p style='font-size: 1.2rem; color: #888;'>Form data received:<br>"
    for k in form.keys():
        formstr += f"<b>{k}</b>: {form[k]}<br>"
    formstr += "</p>"
    link2nada = """
    <p>&nbsp;</p>
    <p style='font-size: 1.2rem;'>
    <a href='/nada'>The meaning of <strong>Nothing...</strong></a>
    <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
    <a href='/test_visitors'><strong>Stress Test</strong></a>
    </p>
    <hr>
    <p style='font-size: 1.2rem;'>
    <a href='/echoroom.html'><strong>Echo Websocket App</strong></a>
    <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
    <a href='/chatroom.html'><strong>Have some chat!</strong></a>
    </p>
    <hr>
    <p style='font-size: 1.2rem;'>
    <a href='/img'><strong>Images</strong></a>
    <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
    <a href='/videos'><strong>Videos</strong></a>
    <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
    <a href='/muzik'><strong>Music</strong></a>
    <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
    <a href='/docs'><strong>Documents</strong></a>
    </p>
    <hr>
    <p style='font-size: 1.2rem;'>
        <a href='/oxi_info.php'><strong>PHP Info</strong></a>
        <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
        <a href='/login_test'><strong>Form Handling Test / CGI-PHP (POST)</strong></a>
    </p>
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Hello, World!</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                font-size: 1.1rem;
                background-color: #f0f0f0;
                margin: 0;
                padding: 1rem;
            }}
            a {{
                text-decoration: none; 
                font-weight: bold; 
                color: green;
            }}  
        </style>
    </head>
    <body>    
    <h1 style="text-align: center; margin-top: 1.5rem; color: steelblue; font-family: 'Arial', sans-serif;">
        Hello from {app.name} / v.{app.version}!
    </h1>
    <p style="font-size: 2rem; font-weight: bold; color: #333;">You're visitor # {visitors}!</p>
    {formstr}
    {link2nada}
    </body>
    </html>
    """

tlock = threading.Lock()
connections = []
messages = []
num_connected = multiprocessing.Value('i', 0)

@app.websocket('/chat')
async def do_some_chat(ws: WebSocket):  
    global num_connected 

    async def send_connected_list():
        userslist = list(filter(lambda name: name is not None, map(lambda conn: conn.username, connections)))
        await send2all({'type': 'users.list', 'list': userslist})

    async def send2all(msg):
        dirty_list: bool = False
        for conn in connections:
            try:
                if len(msg) and (conn.application_state == CONNECTED):
                    await conn.send_json(msg)
                    # print(f"Sent message: '{msg.get('message', '')}' from {msg.get('user', '')} to {conn.name}")
                else:
                    connections.remove(conn)
                    dirty_list = True
            except Exception as exc:
                msg = f"\nCouldn't send message to client {conn.name} due to error: {exc.__class__.__name__}: {exc}"
                print(msg)
                try:
                    conn.close()
                except:
                    pass
                connections.remove(conn)
                dirty_list = True
        
        if dirty_list:
            await send_connected_list()

    def random_color():
        return random.choice(['#008000', '#808000', '#0000FF', '#000080', '#FF00FF', '#A52A2A', '#FF8C00', '#808080'])

    try: 
        await ws.accept()
    except:
        return
    
    with num_connected.get_lock():
        num_connected.value += 1
        ws.name = f"Conn-{str(num_connected.value).zfill(5)}"
    with tlock:
        connections.append(ws)
        print(f"\nConnection {ws.name} accepted.")
        # with mlock:
        for msg in messages[-100:]:
            try:
                await ws.send_json(msg)
                # print(f"Sent message: '{repr(msg)}' to {ws.name}")
            except:
                # print(f"\nError sending previous messages to {ws.name}")
                # ws.close()
                connections.remove(ws)
                return await send_connected_list()
    while True:
        msg = None
        try:
            msg =await ws.receive_json()
        except:
            print(f"\nError receiving message in {ws.name}")
            # ws.close()
            connections.remove(ws)
            return await send_connected_list()

        print(f"Received {repr(msg)} from {ws.name}")
        if hasattr(msg, 'get'):
            msg_type = msg.get('type', None)
            if not msg_type:
                continue
        else:
            continue
        if msg_type == 'chat.msg':
            msg.update({'user_conn': ws.name, 'color': ws.color if hasattr(ws, 'color') else random_color()})
            with tlock:
                messages.append(msg)
                await send2all(msg)
        elif msg_type == "register.user":
            ws.username = msg.get('user')
            ws.color = msg.get('color', random_color())
            msg.update({'color': ws.color})
            try:
                await ws.send_json(msg)
            except:
                print(f"\nError sending message in {ws.name}")
                # ws.close()
                connections.remove(ws)
                return await send_connected_list()
            await send2all({'type': 'chat.msg', 'user': 'Admin', 'color': 'blue', 'message': f'Say hi to {ws.username}'})
            await send_connected_list()
        elif msg_type == "register.color":
            ws.color = msg.get('color', random_color())
            try:
                await ws.send_json(msg)
            except:
                print(f"\nError sending message in {ws.name}")
                # ws.close()
                connections.remove(ws)
                return await send_connected_list()
            print(f"Register color change for {ws.name}/{ws.username} to {ws.color}")
        else:
            print(f"Received a message type I don't know: '{msg_type}'\nSending it to the bin.")
            # await ws.send_json(msg)

@app.websocket("/echo")
async def echo(ws:WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_text()
        if len(data) == 0:
            continue
        # print(f"Eureka! Received: {data}")
        now = datetime.now()
        await ws.send_text(f"{data} - [Received: {now.strftime('%H:%M:%S')}]")
        await asyncio.sleep(0.01)


@app.get("/nada", content_type="text/plain")
async def nada():
    return "Ex nihilo nihil fit."

@app.get("/visitors", content_type="text/plain")
async def get_visitors():
    global visitors
    await asyncio.sleep(0.1)  # Simulate some processing delay
    visitors += 1
    return f"{visitors}"

@app.get("/fvisitors", content_type="text/plain")
async def get_fvisitors():
    global visitors
    # await asyncio.sleep(0.1)  # Simulate some processing delay
    visitors += 1
    return f"{visitors}"

@app.get("/login_test")
async def login_test():
    return await app.redirect("/login.html")

@app.get("/test_visitors")
async def test_visitors():
    lines = ""
    path = f"{os.path.dirname(os.path.abspath(__file__))}{sep}static{sep}test_visitors.html"
    with open(path, "r", encoding="utf-8") as fp:
        lines = fp.read()
    return lines

@app.post("/handle_form")
async def handle_form():
    global visitors
    visitors += 1

    ret = """
    <style>
        body {
            font-family: Arial, Helvetica, sans-serif;
        }
    </style>
""" 
    content_type = to_bytes(app.scope and app.scope.get("_dict_headers", {}).get(b'content-type', 'Unknown')).decode('latin-1')
    ret += f"<h2><strong style='color: steelblue;'>Content-Type:&nbsp;</strong>{content_type}</h2><hr>"
    for form in app.forms:
        if "filename" in form:
            ret += f"<h3><strong style='color: steelblue;'>File:&nbsp;</strong>{form.get('filename', 'NN')}</h3>"
            ret += f"<h3><strong style='color: steelblue;'>Length:&nbsp;</strong>{bytes_to_human_readable(form.get('content-length', 0))}</h3>"
            mimetype = types_map.get(os.path.splitext(form.get('filename'))[1])
            if mimetype and mimetype.startswith("image"):
                encoded_img = encode_image(form.get('content'), mimetype)
                ret += f'<p><img src="{encoded_img}" style="max-width: 640px;" /></p>'
            elif mimetype and mimetype.startswith("text"):
                ret += f"<p><textarea readonly style='width: 90%; height: 15rem; font-size: 1.4rem;'>{form.get('content').decode('latin-1')}</textarea></p>"
            else:
                ret += f"<h3><strong style='color: steelblue;'>{form.get('name', 'NN')}</strong> = {form.get('content', b'Niente').decode('latin-1')}</h3>"
        else:
            for k, v in form.items():
                ret += f"<h3><strong style='color: steelblue;'>{k}</strong> = {v.decode('latin-1') if k == 'content' else v}</h3>"
        ret +="<hr>"
    ret += "<br><p style='text-align: center;'><button style='font-size: 1.5rem;' onclick='history.back();'>Back</button></p>"
    return ret


test_visitors.__doc__ = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>OxiServer Concurrency Test</title>
    <style>
        body { font-family: 'Arial', sans-serif; text-align: center; margin-top: 3rem; background: #f4f7f6; }
        .card { background: white; padding: 2rem; border-radius: 10px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        input, button { font-size: 1.2rem; padding: 0.5rem; margin: 0.5rem; border-radius: 5px; border: 1px solid #ccc; }
        button { background: steelblue; color: white; cursor: pointer; border: none; font-weight: bold; }
        button:hover { background: #3a6073; }
        #resultado { font-size: 1.5rem; font-weight: bold; color: #333; margin-top: 1.5rem; display: block; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color: steelblue;">Julia-OxiServer Stress Test</h2>
        <p>Define la cantidad de peticiones concurrentes a disparar:</p>
        <input type="number" id="nreqs" value="50" min="1" max="1000">
        <button onclick="sendRequests()">Disparar Fetch</button>
        <span id="resultado">Esperando acción...</span>
        <br>
        <label for="current" style="font-size: 1.2rem; color: #555;">Visitantes:</label>
        <span 
            style="padding: 10px; border: 1px solid; border-radius: 5px; border-color: steelblue; font-weight: bold; margin-top: 1.5rem; display: inline-block;" 
            id="current"
        >
            0
        </span>
    </div>

    <script>
        async function sendRequests() {
            const nreqs = parseInt(document.getElementById('nreqs').value);
            const resultadoSpan = document.getElementById('resultado');
            const currentSpan = document.getElementById('current');
            resultadoSpan.innerHTML = "🌀 Procesando ráfaga...";
            
            const start = performance.now();
            
            // Creamos un array de promesas fetch de ejecución inmediata
            const promesas = [];
            for (let i = 0; i < nreqs; i++) {
                promesas.push(
                    fetch('/fvisitors')
                        .then(res => res.text())
                        .catch(err => "Error")
                );
            }
            
            // Esperamos cooperativamente a que todas impacten y regresen
            const respuestas = await Promise.all(promesas);
            const end = performance.now();
            
            // Filtramos las exitosas para ver si hubo pérdidas (respuestas vacías)
            const exitosas = respuestas.filter(t => t !== "Error" && t.trim() !== "").length;
            const tiempoTotal = ((end - start) / 1000).toFixed(3);
            
            resultadoSpan.innerHTML = `✅ ¡Ráfaga Completada!<br>
                Recibidas: <span style="color: green;">${exitosas}/${nreqs}</span><br>
                Tiempo: <span style="color: steelblue;">${tiempoTotal}s</span>`;
            currentSpan.innerHTML = respuestas[respuestas.length - 1] || "0";
        }
    </script>
</body>
</html>
"""    

@app.get('/links_list')
async def ll():
    return app.links_list()

@app.get('/test_error')
async def get_test_error():
    frm_pre_template = """
    <style>
        body {
            background: #f0f0f0;
        }
        div, input, select, option, button {
            font-size: 1.5rem;
        }
    </style>
    <div>
    <form method="POST">
        <p>
            <label>Code &nbsp;</label>
            <select name="code">
"""
    frm_post_template = """
            </select>    
        </p>
        <p>
            <label>Message &nbsp; </label>
            <input type="text" name="err_msg" value="Something went veeery wrong!" style="width: 50rem;" />
        </p>
        <p>
            <input type="reset" value="Reset" />
            <input type="submit" value="Submit" />
        <p>
    </form>
    </div>
    <hr>
    <div style="text-align: center;">
        <button onclick="location.href='/';">Home</button>
    </div>
"""
    options = ""
    for entry in HTTPStatus:
        options += f'<option value="{entry.value}">{entry.value} {entry.phrase}</option>' if entry.value > 399 else ""

    return f"{frm_pre_template}{options}{frm_post_template}"

@app.post('/test_error')
async def post_test_error():
    code = app.form.get('code', 404)
    err_msg = app.form.get('err_msg', 'Unknown error.')
    await app.redirect(f"/raise/{code}?err_msg={err_msg}")

app.mount(wsgi_app, mounted_path="/wsgi")
app.mount(flask_app, mounted_path="/flask")
# app.mount(flask_app, mounted_path="/flask_json", src_path="/flask_json")
app.mount(simple_asgi_app, mounted_path="/simple_asgi")
app.mount(fast_app, mounted_path="/fast_app")


def main():
    filedir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(filedir)
    import subprocess
    subprocess.run('clear')
    run(app, host='0.0.0.0', port=8086)

if __name__ == "__main__":
    # asyncio.run(run_dev_server(app, host="0.0.0.0", port=8086))
    main()