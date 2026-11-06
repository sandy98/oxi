#!/usr/bin/env python3
# -*- coding: utf_8 -*-

# pyright: reportMissingImports=false

import os, sys, asyncio #, time
# from time import strftime

# try:
#     import requests
# except:
#     pass

# os.sys.path.append(os.getcwd())

try:
    from tina.tinaserver import tina_port, run_dev_server, demo_app, static_app, TinaHandler, strftime_template, enctypes
except ImportError:
    from tinaserver import tina_port, run_dev_server, demo_app, static_app, TinaHandler, strftime_template, enctypes


tpl = strftime_template.replace(",", "").replace(" ","_")

# def timeit(times, *, path="", host='http://savos.sytes.net', port=tina_port):
#      print(f"Starting {times} calls to TinA Server")
#      t1 = time.time()
#      for i in range(times):
#          r = requests.get(f"{host}:{port}{path}")
#          print(".", end="")
#          if r.status_code != 200:
#              print(f"Error {r.status_code} ocurred during iteration {i}")
#      t2 = time.time()
#      print(f"\n{times} calls to TinA Server took  {t2 - t1} seconds")


def pad2(num):
    if len(str(num)) == 1:
        return f"0{num}"
    else:
        return str(num)
    
async def formhandler(scope, receive, send):
    if TinaHandler.config == {}:
        print("Reloading HttpRequesHandler config from formhandler")
        TinaHandler.load_config()
    body = b"""
    <style>
        body {
            font-family: sans-serif;
        }
        a {
            color: steelblue;
            text-decoration: none;
            font-weight: bold;
            font-family: monospace;
            font-size: 120%;
        }
        textarea {
            width: 80em;
            height: 12em;
        }
    </style>
    <hr/>
    <p><a href="/uploads">Uploads</a></p>
    <p><a href="/tinademo">Demo</a></p>
    <p><a href="/">Back Home</a></p>
    <hr/>
    <form method="POST" action="/uploader" enctype="application/x-www-form-urlencoded">
        <p>
        <label for="txt-usr">User: </label>
        <input type="text" name="usr" id="txt-usr" />
        </p>
        <p>
        <label for="txt-passwd">Passwd: </label>
        <input type="password" name="passwd" id="txt-passwd" />
        </p>
        <p>
        <input type="submit" value="Submit" />
        <input type="reset" value="Reset" />
        </p>
    </form>
    <hr/>
    <form method="POST" action="/uploader" enctype="multipart/form-data">
        <p>
        <label for="txt-title">Title: </label>
        <input type="text" name="title" id="txt-title" />
        </p>
        <p>
        <label for="input-file">File: </label>
        <input type="file" name="fileupload" id="input-file" />
        </p>
        <p>
        <input type="submit" value="Submit" />
        <input type="reset" value="Reset" />
        </p>
    </form>
    <hr/>
    """

    method = scope.get("method")
    path = scope.get('path')
    
    if path == '/tinademo':
        return await demo_app(scope, receive, send)
    if path != '/' and path != '/uploader':
        return await static_app(scope, receive, send)
    
    if method.lower() == 'get':
        body += b"<p><textarea>You say goodbye, I say hello!\r\n</textarea></p><hr/>"
        form = await TinaHandler.form(scope, b'');
        for k in form:
            newline = f'<p><span style="color: steelblue; font-weight: bold;">{k}</span> = <span>{form[k]}</span></p>'
            body += newline.encode('utf_8')
        body += b"<hr/>"
    elif method.lower() == 'post':
        msg = await receive()
        # logname = f"log/{strftime(tpl)}.txt"
        # with open(logname, 'wb') as fd:
        #     fd.write(msg.get('body')[:int(TinaHandler.config.get('chunk-size'))])
        recv = msg.get('body').decode('latin-1')
        content_type = TinaHandler.get_request_header(scope, b'content-type') or b'text/plain'
        body += f"<p>{content_type.decode()}</p>".encode()
        body += f"<p><textarea disabled>{recv[:2 ** 16]}</textarea>".encode()
        form = await TinaHandler.form_list(scope, msg.get('body'));
        if not form:
           body += f'<p style="color: red;">Something horrible happened while retrieving the form</p>'.encode()
        else:    
            for d in form:
                for k in d:
                    try:
                        field_content = ''
                        if k != 'value':
                            field_content = d[k]
                        else:
                            if not d.get('filename'):
                                field_content = d[k].decode()
                            else:
                                field_content = '&lt;File content&gt;'
                        # field_content = '<File content>'
                        newline = f'<p><span style="color: steelblue; font-weight: bold;">{k}</span> = <span>{field_content}</span></p>'
                        # print(newline)
                        body += newline.encode()
                        if k == 'filename':
                            filename = d.get(k)
                            # print(f"Got filename: {filename}")
                            # os.system(f"mv {logname} ./log/{filename}.log")
                            value = d.get('value')
                            thconfig = getattr(TinaHandler, 'config', {})
                            static_dir = thconfig.get('static-dir')
                            if not static_dir:
                                TinaHandler.load_config()
                                thconfig = getattr(TinaHandler, 'config', {})
                                static_dir = thconfig.get('static-dir')
                            print(f"Static dir is: {static_dir}")
                            static_dir = str(static_dir)
                            filepath = os.path.abspath(static_dir) + os.path.sep + 'uploads' + os.path.sep + filename
                            print(f"Filepath: {filepath}")
                            with open(filepath, "wb") as fd:
                                fd.write(value)
                            filetype = d.get('content-type')
                            print(f"File type is: {filetype}")
                            if filetype.startswith("image"):
                                newline = f'<p><img src="/uploads/{filename}"/></p>'
                                body += newline.encode()
                            elif filetype.startswith("text/html"):    
                                newline = f'<div style="border: solid 1px; width: 80%">{d.get("value").decode("latin-1")}</div>'
                                body += newline.encode()
                            elif filetype.endswith("pdf"):    
                                newline = f'<iframe src="/uploads/{filename}" style="min-height: 75em; border: solid 1px; width: 80%" />'
                                body += newline.encode()
                            else: # filetype.startswith("text/plain"):    
                                newline = f"<p><textarea disabled>{d.get('value').decode('latin-1')[:2 ** 16]}</textarea></p>"
                                body += newline.encode()
                    except Exception as exc:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        print(f"Se ha producido una excepción en linea {'exc_tb.tb_lineno'} al procesar el formulario: {exc}\n")
                          

                body += b"<hr/>"  
    else:
        body += b"<p><textarea>No entiendo que mierda quieres!\r\n</textarea></p>"  

    body += b"""<script>
        document.querySelectorAll("form").forEach(f => f.action = f.action + location.search);
    </script>
    """
    content_l = str(len(body)).encode('latin-1')
    headers = [(b'content-type', b'text/html; charset=utf-8'), (b'content-length', content_l)]
    dictstart = {'type': "http.response.start", 'status': 200, 'headers': headers}
    dictbody = {'type': "http.response.body", 'body': body, 'more_body': False}
    # print(f"Sending response start with status = {dictstart.get('status')}")
    await send(dictstart)
    # print(f"Sending response body with content-length = {content_l.decode('latin-1')}")
    return await send(dictbody)

async def runapp():
    await run_dev_server(formhandler, '0.0.0.0', tina_port)

def main():
    asyncio.run(runapp())

if __name__ == '__main__':
    main()