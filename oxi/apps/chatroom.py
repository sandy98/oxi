#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, asyncio, random, multiprocessing, threading
from pathlib import Path

currfile = Path(__file__)
currdir = currfile.parent
appspath = currdir.parent
oxipath = appspath.parent
sys.path.insert(0, str(appspath))
sys.path.insert(0, str(oxipath))

# from oxi import server
from oxi.app import OxiApp
from oxi.static import static_app
from oxi.tina.websocket import WebSocket, CONNECTED
# from tinaserver import TinaHandler, run_server, static_app, tina_port
# from websocket import WebSocket, WSDisconnection ,CONNECTED

os.chdir(currdir)
# print(currdir)

async def nullapp(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain'), (b'content-length', b'4')]})
    await send({'type': 'http.response.body', 'body': b'null', 'more_body': False})

# chatapp = TinApp(nextcall=nullapp)
chatapp = OxiApp()
chatapp.next = static_app

@chatapp.get('/')
async def home():
    # with open('static/chatroom.html', 'r') as fd:
    #     # return fd.read().replace('<!--STYLE-->', TinaHandler.get_default_style())
    #     return fd.read()
    await chatapp.redirect('/chatroom.html')

tlock = threading.Lock()
connections = []
messages = []
num_connected = multiprocessing.Value('i', 0)

@chatapp.websocket('/chat')
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
                    print(f"Sent message: '{msg.get('message', '')}' from {msg.get('user', '')} to {conn.name}")
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
                print(f"Sent message: '{repr(msg)}' to {ws.name}")
            except:
                print(f"\nError sending previous messages to {ws.name}")
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

def main():
    # TinaHandler.load_config()
    from oxi.server import run
    run(chatapp, '0.0.0.0', 8086)

if __name__ == '__main__':
    main()