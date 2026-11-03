#-*- coding: utf_8 -*-
import random

async def test_app(scope, _, send):
    path = scope.get('path')
    name = path[1:].title() if path != "/" else "World!" 
    response = f"<h1>Hello, {name}!</h1>".encode('latin-1')
    headers = [
                (b'content-length', str(len(response)).encode('latin-1')),
                (b'content-type', b'text/html; charset=latin-1')
               ] 
    startdict = {
        'type': 'http.response.start',
        'status': 200,
        'headers': headers
    }
    bodydict = {
        'type': 'http.response.body',
        'body': response,
        'more_body': False
    }

    await send(startdict)
    return await send(bodydict)

async def not_found(scope, _, send):
    path = scope.get('path')
    response = f"<h3>No sea pelotudo, {path} no existe!</h3>".encode('latin-1')
    headers = [
                (b'content-length', str(len(response)).encode('latin-1')),
                (b'content-type', b'text/html; charset=latin-1')
               ] 
    startdict = {
        'type': 'http.response.start',
        'status': 404,
        'headers': headers
    }
    bodydict = {
        'type': 'http.response.body',
        'body': response,
        'more_body': False
    }

    await send(startdict)
    return await send(bodydict)

def wsgi_app(environ, start_response):
    path = environ.get('PATH_INFO')
    name = path[1:].title() if path != "/" else "World!" 
    response = f"<h1>Hello, {name}!</h1>".encode()
    headers = [
                ('content-length', len(response)),
                ('content-type', 'text/html; charset=utf-8')
               ] 

    start_response("200 OK", headers)
    return response

def application(environ, start_response):
    colors = ['red', 'steelblue', '#008f00']
    pth = environ.get('path_info'.upper())
    li = []
    if pth == '/':
        li = [f'<h1 style="color: {random.choice(colors)}; margin-top: 1em;font-family: sans-serif; text-align: center;">'.encode('utf-8')]
        li.append(b'Greetings, Universe!')
        li.append(b'</h1><hr>')
        li.append(b'<p style="text-align: center"><button onclick="location.href = location.href;">Reload</button></p>')
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8'),
                                  ('Content-Length', str(len(b''.join(li))))])
    else:
        li = [f"<h2><span style='color: red;'>404</span> '{pth}' Not found</h2>".encode('utf-8')]
        start_response('404 Not found', [('Content-Type', 'text/html; charset=utf-8'),
                                  ('Content-Length', str(len(b''.join(li))))])
    return li

if __name__ == '__main__':
    # import uvicorn
    # uvicorn.run(wsgi_app, port=8000)
    import os, sys
    parent_path = "/home/ernesto/Programas/2024/python/cadrapp/tina"
    sys.path.append(parent_path)
    from tinaserver import run_dev_server, asyncio
    asyncio.run(run_dev_server(wsgi_app, port=8000))