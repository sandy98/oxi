#!/usr/bin/env python3
#-*- coding: utf-8 -*-

# pyright: reportMissingImports=false
# pyright: reportGeneralTypeIssues=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportFunctionMemberAccess=false
# pyright: reportReturnType=false
# pyright: reportArgumentType=false
# pyright: reportOptionalIterable=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportPossiblyUnboundVariable=false
# pyright: reportAssignmentType=false


import os, sys, signal, asyncio, io, time, json, socket, re, io, errno, gzip, inspect #, contextlib
import struct, hashlib, base64
from urllib.parse import urlparse, unquote, parse_qsl #, quote, parse_qs, urlencode, urlunparse
from http import HTTPStatus
from mimetypes import guess_type
from typing import Coroutine, Callable, Any
from functools import reduce
# from concurrent.futures import ProcessPoolExecutor
import multiprocessing, threading

try:
    from tina.utils import SmartDict
    from tina import __version__ as tina_version
except:
    from utils import SmartDict
    from __init__ import __version__ as tina_version

try:       
    from mp4parser import Mp4
except:
    try:
        from tina.mp4parser import Mp4
    except:
        with open("log/error.log", "r+") as fd:
            fd.write("Warning: Mp4 class could not be imported.\n")

# os.chdir(os.path.split(__file__)[0])

try:
    if __name__ == '__main__':
        import subprocess
        subprocess.run("clear")
    import uvloop # pyright: ignore[reportMissingImports]
    if __name__ == '__main__':
        print(f"UVloop imported successfully.")
    # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        uvloop.install()
    if __name__ == '__main__':
        print(f"Event loop policy successfully set to UVloop.\n")
except:
    if __name__ == '__main__':
     print("UVloop not found\n")

tina_port = int("".join(list(map(lambda x: str(ord(x)), "TinA")))) // 1000000

g_lock = multiprocessing.Lock()
t_lock: threading.Lock = threading.Lock()

async def get_visitors() -> int:
    with t_lock:
        try:
            with open(f"{os.path.abspath('.')}{os.path.sep}log{os.path.sep}visitors.txt") as vf:
                return int(vf.read())
        except:
            return 0
        
async def set_visitors(n: int) -> None:
    with t_lock:
        try:
            with open(f"{os.path.abspath('.')}{os.path.sep}log{os.path.sep}visitors.txt", "w") as vf:
                vf.write(str(n))
        except:
            pass

def to_bytes(text, encoding='utf-8'): 
    if type(text) == bytes:
        return text
    elif type(text) == int or type(text) == float:
        return str(text).encode(encoding)
    elif isinstance(text, (tuple, list)):
        return list(map(to_bytes, text))
    else:
        return str(text).encode(encoding)

enctypes: tuple = (b"application/x-www-form-urlencoded", 
                   b"multipart/form-data", 
                   b"application/json",
                   b"text/plain")

strftime_template = "%a, %d  %b %Y %X %Z"

[major, minor, release] = tina_version.split('.')
default_config = {"pyinfo": {"python-version": "3.10.12", "python-implementation": "CPython"}, 
"serverinfo": {"version": tina_version, 
               "major-version": int(major), 
               "minor-version": int(minor), 
               "release-version": int(release), 
               "server-name": "TinA",
               "debug-mode": True, 
               "dirlisting-enabled": True, 
               "cgi-enabled": True, 
               "cgi-dir": "cgi-bin", 
               "static-dir": "static",
               "sessions-dir": "sessions", 
               "chunk-size": 32768, 
               "redirects": {"wikipedia": "https://wikipedia.org", 
                             "google": "https://google.com", 
                             "tiobe": "https://www.tiobe.com/tiobe-index/", 
                             "realpython": "https://realpython.org", "cloaked": True
                            }, 
                "proxy_pass": {"localtest": "http://localhost:8000/",
                               "failtest": "http://localhost:9999/", 
                               "savos8000": "http://savos.sytes.net:8000",
                               "comics": "http://savos.sytes.net:20386",
                               "coronando": "http://savos.sytes.net:3010"
                            }
                }
}

wouldbethis = """Gur Mra bs Clguba, ol Gvz Crgref

Ornhgvshy vf orggre guna htyl.
Rkcyvpvg vf orggre guna vzcyvpvg.
Fvzcyr vf orggre guna pbzcyrk.
Pbzcyrk vf orggre guna pbzcyvpngrq.
Syng vf orggre guna arfgrq.
Fcnefr vf orggre guna qrafr.
Ernqnovyvgl pbhagf.
Fcrpvny pnfrf nera'g fcrpvny rabhtu gb oernx gur ehyrf.
Nygubhtu cenpgvpnyvgl orngf chevgl.
Reebef fubhyq arire cnff fvyragyl.
Hayrff rkcyvpvgyl fvyraprq.
Va gur snpr bs nzovthvgl, ershfr gur grzcgngvba gb thrff.
Gurer fubhyq or bar-- naq cersrenoyl bayl bar --boivbhf jnl gb qb vg.
Nygubhtu gung jnl znl abg or boivbhf ng svefg hayrff lbh'er Qhgpu.
Abj vf orggre guna arire.
Nygubhtu arire vf bsgra orggre guna *evtug* abj.
Vs gur vzcyrzragngvba vf uneq gb rkcynva, vg'f n onq vqrn.
Vs gur vzcyrzragngvba vf rnfl gb rkcynva, vg znl or n tbbq vqrn.
Anzrfcnprf ner bar ubaxvat terng vqrn -- yrg'f qb zber bs gubfr!"""

isthis = """
The Zen of Python, by Tim Peters

Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one-- and preferably only one --obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea -- let's do more of those!
"""

easter_eggs = {'/would': wouldbethis, '/this': isthis}

async def handle_echo(_: dict, receive: Callable, send: Callable) -> None:
    msg = await receive()
    await send(msg)

async def handle_echo_stand_alone(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    data = await reader.read(100)
    message = data.decode('utf-8')
    addr = writer.get_extra_info('peername')

    print(f"Received {message!r} from {addr!r}")

    print(f"Send: {message!r}")
    writer.write(data)
    try:
        await writer.drain()
    except:
        pass

    print("Close the connection")
    writer.close()
    await writer.wait_closed()

######################################################################################

class TinaHandler():
    """Receives requests, parses them and handles them to the application to be responded."""

    config = {}

    headers_sent = False

    def __init__(self, app: Callable|None = None, cfg_file: str|None = None, *, 
                 multiprocess=False, multithread=True, num_processes= None, num_threads= None):
        self.response_headers = []
        self.app = app or self.default_app

        if not self.config:
            if cfg_file:
                self.load_config(cfg_file)
        self.__class__.__dict__['multiprocess'] = multiprocess
        self.__class__.__dict__['multithread'] = multithread
        self.__class__.__dict__['num_processes'] = num_processes
        self.__class__.__dict__['num_threads'] = num_threads
    
    async def  __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        scope = await TinaHandler.get_scope(reader, writer, self)
        # print(f"get_scope sent this: {scope} to __call__")
        if scope == {} or scope is None:
            # print("get_scope sent an empty dict, __call__ closing socket. Bye.")
            writer.close()
            await writer.wait_closed()
            return

        if scope["type"] == "http":
            await self.http_handler(scope, reader, writer)
        elif scope["type"] == "websocket":
            await self.websocket_handler(scope, reader, writer)
        else:
            writer.close()
            await writer.wait_closed()

    async def http_handler(self, scope, reader, writer):

        async def receive()-> dict:
            if not scope or scope == {}:
                return {}

            if len(scope.get('request_body')): # receive was run previously so, just deliver the saved request body
                print(f"{scope.get('path')}: request body already delivered.") 
                body = scope.get('request_body')
                return {
                    "type": "http.request",
                    "body": body,
                    "length": len(body),
                    "more_body": False,
                }

            content_length = await TinaHandler.get_content_length(scope)
            body = b''
            morebody = b''
            if scope.get('method').lower() not in ['get', 'head', 'options', 'delete']:
                while True:
                    try:
                        # morebody = await asyncio.wait_for(reader.read(int(self.__class__.config.get('chunk-size'))), timeout=5)
                        morebody = await asyncio.wait_for(reader.read(8192), timeout=1)
                        # print(f"Received a chunk of {len(morebody)} bytes.")
                        body += morebody
                        await asyncio.sleep(0)
                        if len(body) >= content_length or len(morebody) == 0:
                            break
                    except asyncio.TimeoutError:
                        print("Timed out waiting for request body")
                        break    

            scope["request_body"] = body

            return {
                "type": "http.request",
                "body": body,
                "length": len(body),
                "more_body": False,
            }

        async def send(event: dict)-> None:
            # App's sending the response headers
            if not scope or scope == {}:
                return
            if event["type"] == "http.response.start":
                self.response_headers = await TinaHandler.get_response_headers(scope, event)
                return
            # App's sending the response body
            elif event["type"] == "http.response.body":
                # The headers should only be pushed once the body is received
                if self.response_headers:
                    writer.writelines(self.response_headers)
                    self.response_headers = []
                else:
                    pass #Error handling for trying to send response body without prior response headers setting
            else:
                pass # Error handling for unrecognized event type

            body = event.get("body")
            try:
                writer.write(body) 
                await writer.drain()
            except Exception as exc:
                print(f"Exception occured while sending data to remote host on route '{scope.get('path')}': {exc}")
                raise 

            if event.get("more_body", False) is False:
                # Close connection
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as exc:
                    print(f"Exception occured while closing connection to remote host: {exc}")
                    raise

        try:
            if TinaHandler.is_wsgi(self.app):
                app: Callable = await TinaHandler.wsgi2asgi(scope, receive, send, self.app)
                # print("Returning content via WSGI adapter")
                await app(scope, receive, send)
            else:
                # print("Returning content via ASGI function")
                await self.app(scope, receive, send)
        except Exception as exc:
            etype, _, tb = sys.exc_info()
            info = f"""Exception '{etype}' occurred while sending response
            at line {tb.tb_lineno} of file {tb.tb_frame.f_code.co_filename}.""" # type: ignore
            print(info)
            response_body = f"""
            <h2 style="font-family: sans-serif; text-align: center">
                <span style="color: red;">500</span>
                Internal server error '<span style="color: red;">{exc}</span>' 
                occurred while processing '{scope.get('path')}'
            </h2>
            """.encode('utf-8')
            content_length = len(response_body)
            headers = [(b'content-type', 'text/html; charset=utf-8'), (b'content-length', content_length)]
            startdict = {
                'type': 'http.response.start',
                'status': 500,
                'headers': headers
            }
            bodydict = {
                'type': 'http.response.body',
                'body': response_body,
                'more_body': False
            }
            await send(startdict)
            await send(bodydict)

    async def websocket_handler(self, scope, reader, writer):

        def make_upgrade_response():
            guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            dict_headers = scope["_server.dict_headers"]
            key = dict_headers["sec-websocket-key"]
            key_hash = hashlib.sha1(f"{key}{guid}".encode())
            accept = base64.b64encode(key_hash.digest())

            # Complete HTTP handshake and upgrade to websocket connection
            headers = [
                b"HTTP/1.1 101 Switching Protocols\r\n",
                b"Upgrade: websocket\r\n",
                b"Connection: Upgrade\r\n",
                b"Sec-WebSocket-Accept: " + accept + b"\r\n",
                b"\r\n",
            ]

            return headers

        async def read_websocket_frame():
            # Read frame header
            try:
                header = await reader.read(2)
            except Exception as exc:
                print(f"Exception occurred while trying to read frame: {repr(exc)}")
                raise

            unpacked = struct.unpack("<BB", header)
            fin = (unpacked[0] & (1 << 7)) > 0
            opcode = unpacked[0] & 0x0F
            mask = (unpacked[1] & (1 << 7)) > 0
            payload_len = unpacked[1] & 0x7F

            if payload_len == 126:
                l = await reader.read(2)
                u = struct.unpack("<H", l)
                payload_len = u[0]
            elif payload_len == 127:
                l = await reader.read(8)
                u = struct.unpack("<Q", l)
                payload_len = u[0]

            if mask:
                masking_key = await reader.read(4)

            payload = await reader.read(payload_len)

            if mask:
                payload = bytes(payload[i] ^ masking_key[i % 4] for i in range(len(payload))) # type: ignore

            return fin, opcode, payload

        def make_frame(opcode, payload=b''):
            frame = bytearray()
            frame.append(0x80 | opcode)  # FIN bit set and the opcode for ping (0x9)

            length = len(payload)
            if length < 126:
                frame.append(length)
            elif length < (1 << 16):
                frame.append(126)
                frame.extend(length.to_bytes(2, byteorder='big'))
            else:
                frame.append(127)
                frame.extend(length.to_bytes(8, byteorder='big'))

            frame.extend(payload)
            return frame

        def make_websocket_frame(event: dict):
            payload = b""
            opcode = -1

            if event.get("text") is not None:
                payload = event.get("text", "").encode()
                opcode = 1
                # frame.extend(bytes([(1 << 7) | 1]))  # FIN=1 + opcode=1
            elif event.get("bytes") is not None:
                payload = event.get("bytes", b"")
                opcode = 2
                if event.get("type") == "websocket.ping":
                    payload = payload[:125]
                    opcode = 9
                if event.get("type") == "websocket.pong":
                    payload = payload[:125]
                    opcode = 10

            return make_frame(opcode, payload)
        
        connect_sent = False

        async def receive():
            nonlocal connect_sent

            event = {}

            if not connect_sent:
                connect_sent = True
                return {"type": "websocket.connect"}

            fin, opcode, payload = await read_websocket_frame()

            if opcode == 1:
                event = {"type": "websocket.receive", "text": payload.decode()}
            elif opcode == 2:
                event = {"type": "websocket.receive", "bytes": payload}
            elif opcode == 8:
                close_code = 1005  # Default
                if len(payload):
                    u = struct.unpack(">H", payload)
                    close_code = u[0]
                return {"type": "websocket.disconnect", "code": close_code}
            elif opcode == 9:
                event = {"type": "websocket.ping", "bytes": payload}
#                print("\nPING frame received.")
#                print(f"fin: {fin} - opcode: {opcode} - payload: {payload}")
            elif opcode == 10:
                event = {"type": "websocket.pong", "bytes": payload}
#                print("\nPONG frame received.")
#                print(f"fin: {fin} - opcode: {opcode} - payload: {payload}")
            else:
                raise Exception(f"Opcode not implemented: {opcode}")

            if not fin:
                raise Exception("Fragmented frames not supported")

            return event

        async def send(event):
            ev_type = event.get("type", "")
            if ev_type == "websocket.accept":
                # App's is requesting to accept the connection request
                response = make_upgrade_response()
                try:
                    writer.writelines(response)
                    await writer.drain()
                except Exception as exc:
                    print(f"Exception occurred in send websocket coroutine accepting connection: {exc}")
                    raise
            elif ev_type == "websocket.ping" or ev_type == "websocket.pong" or ev_type == "websocket.send":
                # App's sending data
                frame = make_websocket_frame(event)
                try:
                    writer.write(frame)
                    await writer.drain()
                except Exception as exc:
                    print(f"Exception occurred in send websocket coroutine while sending frame: {exc}")
                    raise
            elif ev_type == "websocket.close":
                # App's requesting to close the connection
                code = event.get("code", 1000)
                try:
                    writer.write(bytes([1 << 7 | 8]))  # opcode 8
                    writer.write(bytes([2]) + code.to_bytes(2, "big"))
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                except Exception as exc:
                    print(f"Exception occurred in send websocket coroutine while closing connection: {exc}")
                    raise

        # Invoke the app!
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            etype, _, tb = sys.exc_info()
            info = f"""Exception '{etype}' occurred while sending response
            at line {tb.tb_lineno} of file {tb.tb_frame.f_code.co_filename}.""" # type: ignore
            print(info)
            raise

#####################################################################################################

    async def default_app(self, scope: dict, receive: Callable, send: Callable)-> None:
        return await static_app(scope, receive, send)
  
    @classmethod
    def load_config(cls, file_name: str = None)-> None: # type: ignore
        filename = file_name if file_name else "server_config.json"
        if os.path.exists(filename):
            with open(filename, 'r') as json_fd:
                cls.config = json.load(json_fd).get('serverinfo')
        else:
            cls.config = default_config.get('serverinfo')
        
    @classmethod
    def save_config(cls, file_name: str|None = None)-> None:
        filename = file_name if file_name else "server_config.json"
        with open(filename, 'w') as json_fd:
            json.dump({"serverinfo": cls.config}, json_fd, indent=4)

    @classmethod
    def demo(cls):
        handler = cls(demo_app)
        demo_app.handler = handler # type: ignore
        #print("Instantiating a demo server.\n")
        return handler
    
    @classmethod
    def static(cls):
        handler = cls(static_app)
        static_app.handler = handler # type: ignore
        #print("Instantiating a static server.\n")
        return handler
    
    @classmethod
    def chunks(cls, size:int):
        clsconfig = getattr(cls, 'config', {})
        ch_sz:int|Any = clsconfig.get('chunk-size')
        numchunks = size // ch_sz
        tailen = size %  ch_sz
        body = list(map(lambda n: (n * ch_sz, n * ch_sz + ch_sz), range(numchunks)))
        tail = (numchunks * ch_sz, numchunks * ch_sz + tailen) if tailen else None
        return body, tail

    @staticmethod
    def common_response_headers() -> list:
        return [
            (b'connection', b'keep-alive'),
            (b'date', time.strftime(strftime_template).encode('utf-8')),
            (b'server', f"TinA/{tina_version}".encode('utf-8')),
            (b"accept-ranges",  b"bytes")
        ]

    @staticmethod
    def resource_response_headers(resource: str) -> list:
        stat = os.stat(resource)
        content_type = guess_type(resource)[0] or 'application/x-trash'
        if content_type.startswith('text') or content_type == 'application/json':
            content_type += '; charset=utf-8'
        return [
            (b'content-length', str(stat.st_size).encode('utf-8')),
            (b'content-type', content_type.encode('utf-8')),
            (b'last-modified', time.strftime(strftime_template, time.gmtime(stat.st_mtime)).encode('utf-8')),
        ]
    
    @staticmethod
    def encrypt(word: str):
        return base64.b64encode(hashlib.sha1(word.encode('utf-8')).digest())

    @staticmethod
    def generate_csrf_token():
        return hashlib.sha256(os.urandom(64)).hexdigest()

    @staticmethod
    async def get_content_type(scope: dict):
        boundary = None
        content_type = None
        content_type = TinaHandler.get_request_header(scope, b'content-type')
        if not content_type:
            content_type = TinaHandler.get_request_header(scope, b'content-type'.upper())
        if not content_type:
            content_type = TinaHandler.get_request_header(scope, 'content-type')
        if not content_type:
            content_type = TinaHandler.get_request_header(scope, 'content-type'.upper())

        if not content_type:
            return None, None
        if (content_type.startswith(b'application/x-www-form-urlencoded') 
            or content_type.startswith(b'application/json')):
            return content_type, None
        if content_type.startswith(b"multipart/form-data"):
            try:
                content_type, boundary = content_type.split(b"; ")
                boundary = boundary.split(b"=")[1]
                return content_type, boundary
            except:
                return None, None

    @staticmethod
    async def form_list(scope, body: bytes) -> list:
        boundary = None
        start_boundary = None

        if isinstance(scope, dict):
            query_string = scope.get(b"query_string") or scope.get(b"query_string".upper())
            if query_string is None:
                query_string = scope.get("query_string") or scope.get("query_string".upper())
        else:
            query_string = b''

        query_dict = {}
        response = []
        if query_string and len(query_string):
            try:
                # print(f"Parsing query string: {query_string.decode('latin-1')}")
                query_dict = dict(parse_qsl(query_string.decode('latin-1')))
            except:
                # print(f"Parsing query string: {query_string}")
                query_dict = dict(parse_qsl(query_string))

        if not len(body):
            return [query_dict]
        
        if isinstance(scope, bytes):
            scope = {b'headers': [(b'content-type', scope)]}
        elif isinstance(scope, str):
            scope = {b'headers': [(b'content-type', scope.encode('utf-8'))]}

        try:
            content_type, boundary = await TinaHandler.get_content_type(scope)
            # print(f"Content-Type: {content_type} - Boundary: {boundary}")
            if content_type not in enctypes:
                print(f"{content_type} is not a valid form encoding")
                return []
            if content_type == enctypes[0]:
                response = [query_dict, dict(parse_qsl(body.decode('latin-1'), keep_blank_values=True))]
            elif content_type == b'application/json':
                charset = b'utf-8'
                if b'charset' in content_type:
                    index = content_type.index('charset') # pyright: ignore[reportArgumentType] 
                    _, charset = content_type[index:].split(b"=") 
                response = [query_dict, json.loads(body.decode(charset.decode()))]
            else:
                response = [query_dict]
                start_boundary = b"--" + boundary  # pyright: ignore[reportOperatorIssue]
                # end_boundary = b"--" + boundary + b"--"
            
                body = body[:-4]
                parts = body.split(start_boundary)
                headers_and_payloads = []
                for part in parts[1:-1]:
                    headers, payload = part.split(b'\r\n\r\n', 1)
                    headers_and_payloads = [*headers_and_payloads, (headers, payload[:-2])]

                for h_and_p in headers_and_payloads:
                    newentry = {'content': h_and_p[1], 'content-length': len(h_and_p[1])}
                    headers = h_and_p[0]
                    header_lines = headers.strip().split(b'\r\n')
                    for line in header_lines:
                        lineparts = line.split(b'; ')
                        key, value = lineparts[0].split(b': ')
                        newentry[key.strip().lower().decode('latin-1')] = value.strip().decode('latin-1')
                        for linepart in lineparts[1:]:
                            key, value = linepart.split(b"=")
                            newentry[key.strip().lower().decode('latin-1')] = value.strip(b'"').decode('latin-1')
                    response = [*response, newentry]
            # print(f"Returning response form: {repr(response)}")    
            return response
        except Exception as exc:
            _, _, tb = os.sys.exc_info()
            print(f"Exception '{exc}' occurred while processing form at line {tb.tb_lineno}.")
            return []

    @staticmethod
    # async def form(scope: dict | bytes | str, body: bytes) -> dict:
    async def form(scope, body: bytes) -> dict:
        li = await TinaHandler.form_list(scope, body)
        if not len(li):
            return {}
        else:
            d = li[0]
            rest = li[1:]
            for other_d in rest:
                d.update(other_d)
            # print(d)
            return d

    @staticmethod
    def is_wsgi(callablee: Callable) -> bool:
        if not callable(callablee):
            return False
        params = list(inspect.signature(callablee).parameters.items())
        if len(params) != 2:
            return False
        
        return params[0][0].lower() == "environ" and params[1][0].lower() == "start_response"

    @staticmethod
    def urlencode(form: dict) -> bytes:
        li = []
        for k, v in form.items():
            li.append(f"{k}={v}".encode('latin-1'))
        return b"&".join(li)

    @staticmethod
    def encode_image(image_data, image_type='image/jpeg'):
        img_template = "data:{0};base64,{1}"
        img_string = base64.b64encode(image_data).decode("utf-8")
        return img_template.format(image_type, img_string)

    @staticmethod
    def environ_from_scope(scope: dict):
        environ = {
                    "wsgi.version": (1, 0),
                    "wsgi.url_scheme": scope.get("scheme", "http"),
                    "wsgi.input": io.BytesIO(),
                    # "wsgi.errors": io.BytesIO(),
                    "wsgi.errors": os.sys.stderr,
                    "wsgi.multithread": False,
                    "wsgi.multiprocess": False,
                    "wsgi.run_once": False,
                    "GATEWAY_INTERFACE": "CGI/1.1",
                    "SERVER_SOFTWARE": scope.get("server_software"),
                    "REQUEST_METHOD": scope.get('method', 'get').upper(),
                    "SCRIPT_NAME": os.path.split(scope.get('path', "/"))[1],
                    "PATH_INFO": scope.get('path', '/'),
                    "QUERY_STRING": scope["query_string"].decode("ascii"),
                    "SERVER_PROTOCOL": f'HTTP/{scope["http_version"]}',
                    "SERVER_NAME": scope.get("server_name"),
                    "SERVER_PORT": scope.get("server_port"),
                    "REMOTE_ADDR": scope.get('client', ['127.0.0.1', 0])[0]
        }

        for name, value in scope.get("headers", []):
            name = name.decode("latin1")
            if name == "content-length":
                corrected_name = "CONTENT_LENGTH"
            elif name == "content-type":
                corrected_name = "CONTENT_TYPE"
            else:
                corrected_name = f'HTTP_{name.upper().replace("-", "_")}'
            # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
            value = value.decode("latin1")
            if corrected_name in environ:
                value = environ[corrected_name] + "," + value
            environ[corrected_name] = value

        # scope['_wsgi_environ'] = environ
        return environ

    @staticmethod
    async def scope2environ(scope: dict) -> dict:
        if not '_wsgi_environ' in scope:
            scope['_wsgi_environ'] = TinaHandler.environ_from_scope(scope) 
        environ = scope.get('_wsgi_environ', {}).copy()
        return environ
    
    @staticmethod
    async def wsgi2asgi(scope: dict, receive: Callable, send: Callable, wsgi_callable: Callable) -> Callable:
        environ = await TinaHandler.scope2environ(scope)
        if not environ:
            raise RuntimeError("WSGI environment is not set")
        
        if scope.get('method', 'get').lower() not in ['get', 'head', 'options']:
            # print(f"Trying to retrieve request body to pass it to wsgi.input")
            msg = await receive()
            body = msg.get('body')
            # body += b'\r\n'
            environ['wsgi.input'] = io.BytesIO(body)

        TinaHandler.headers_sent = False

        def start_response(status, headers):
            writer = scope.get('_writer')
            if not writer:
                raise Exception("Internal server error")
            try:
                if TinaHandler.headers_sent:
                    raise Exception("Headers already sent")
                status_code = int(status.split(" ")[0]) if type(status) in [str, bytes] else status
                wsgi_callable.status_code = status_code
                writer.write(f"HTTP/1.1 {status_code} {HTTPStatus(status_code).phrase}\r\n".encode('utf-8'))
                time.sleep(0.05)
                for k, v in headers:
                    writer.write(f"{k}: {v}\r\n".encode('utf-8'))
                    time.sleep(0.05)
                writer.write(b"\r\n")
                time.sleep(0.05)
                TinaHandler.headers_sent = True
            except Exception as exc:
                raise exc
            return writer
                    
        async def asgi_wrapper(scope: dict = scope, receive: Callable = receive, send: Callable = send):
            # if not TinaHandler.headers_sent:
            #     raise Exception("Attempt to send response body without prior sending response headers")
            result = b''
            if inspect.iscoroutinefunction(wsgi_callable):
                result = await wsgi_callable(environ, start_response)
            else:
                task = asyncio.create_task(asyncio.to_thread(wsgi_callable, environ, start_response))
                result = await task
            lresult = []
            for text in result:
                lresult.append(text)
            result = b''.join(lresult)

            method = scope.get('method', 'GET').upper()
            # remote_ip = scope.get('x-real-ip', '')
            remote_ip = scope.get('client', ['unknown','unknown'])[0]
            remote_host = scope.get('remote_host', 'Unknow host')
            pth = scope.get('path', "/")
            status = wsgi_callable.status_code
            print(f"\nWSGI: (PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {status}")
            d = {
                'type': 'http.response.body',
                'body': to_bytes(result),
                'more_body': False
            }
            await send(d)
            TinaHandler.headers_sent = False

        return asgi_wrapper
    
    @classmethod
    async def get_scope(cls, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, handler = None)-> dict:
        request_line = None
        request = None
        retval = None

        remote_addr = writer.get_extra_info('peername')
        remote_ip, remote_port = remote_addr[:2]
        remote_port = int(remote_port) if remote_port else None
        try:
            remote_host = socket.gethostbyaddr(remote_ip)
        except:
            remote_host = ["Unknown host"]

        client = (remote_addr[0], remote_port)

        transport = writer.transport
        sock = transport.get_extra_info('socket')

        local_addr = writer.get_extra_info('sockname')
        local_ip, local_port = local_addr[:2]
        local_port = int(local_port) if local_port else None
        try:
            server_name = socket.gethostbyaddr(local_ip)[0]
        except:
            server_name = "Unknown TinA Server"

        try: 
            request_line = await reader.readuntil(b"\r\n")
            request = request_line.decode('utf-8').rstrip()
            is_request = TinaHandler.is_request_line(request)
            if is_request is False:
                writer.write(request_line)
                await writer.drain()
                # print("Not a valid request line, returning an empty dict as scope.")
                return {}

            method, path, protocol = request.split(" ", 3)
            url = urlparse(path)
            __, http_version = protocol.split("/")
            # headers = await TinaHandler.get_scope_headers(reader)
            headers, dict_headers = await TinaHandler.get_scope_headers(reader)

            retval = SmartDict({
                "server_version": tina_version,
                "server_software": f"TinA (Tiny Asynchronous Server) {'v ' +  tina_version}",
                "server_name": f"TinA/{tina_version}",
                "gateway_interface": "CGI/1.1",
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": http_version,
                "method": method,
                "scheme": "http",
                "path": url.path,
                "query_string": url.query.encode('latin-1'),
                "x-real-ip": remote_ip,
                "remote-host": remote_host[0],
                "remote-port": str(remote_port) if remote_port else "null",
                "server_ip": local_ip,
                "local_port": str(local_port) if local_port else "null",
                "server_port": str(local_port) if local_port else "80",
                "client": client,
                "headers": headers,
                "_server.dict_headers": dict_headers,  # Internal use only
                "_reader": reader, # Internal use only
                "_writer": writer,  # Internal use only
                "_sock": sock,  # Internal use only
                "extensions:": {
                    "type": "echo"
                },
                "request_body": b'',
            })

            if (
                method.upper() == "GET"
                and "Upgrade" in dict_headers.get("connection", "")
                and dict_headers.get("upgrade") == "websocket"
            ):
                sec_websocket_protocol = dict_headers.get("sec-websocket-protocol", "")
                subprotocols = [proto.strip() for proto in sec_websocket_protocol.split(",")]
                retval.update({"type": "websocket", "subprotocols": subprotocols})
            else:
                retval.update({"type": "http", "method": method})
                environ = SmartDict({
                    "wsgi.version": (1, 0),
                    "wsgi.url_scheme": retval.get("scheme", "http"),
                    "wsgi.input": io.BytesIO(),
                    # "wsgi.errors": io.BytesIO(),
                    "wsgi.errors": os.sys.stderr,
                    "wsgi.multithread": cls.multithread,
                    "wsgi.multiprocess": cls.multiprocess,
                    "wsgi.run_once": False,
                    "GATEWAY_INTERFACE": "CGI/1.1",
                    "SERVER_SOFTWARE": retval.get("server_software"),
                    "REQUEST_METHOD": method.upper(),
                    "SCRIPT_NAME": os.path.split(path)[1],
                    "PATH_INFO": url.path,
                    "QUERY_STRING": retval["query_string"].decode("ascii"),
                    "SERVER_PROTOCOL": f'HTTP/{retval["http_version"]}',
                    "SERVER_NAME": retval.get("server_name"),
                    "SERVER_PORT": retval.get("server_port"),
                    "REMOTE_ADDR": remote_ip,
                })

                for name, value in retval.get("headers", []):
                    name = name.decode("latin1")
                    if name == "content-length":
                        corrected_name = "CONTENT_LENGTH"
                    elif name == "content-type":
                        corrected_name = "CONTENT_TYPE"
                    else:
                        corrected_name = f'HTTP_{name.upper().replace("-", "_")}'
                    # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
                    value = value.decode("latin1")
                    if corrected_name in environ:
                        value = environ[corrected_name] + "," + value
                    environ[corrected_name] = value


                retval['_wsgi_environ'] = environ

        except Exception as exc:
            print(f"Exception {exc} happened in get_scope, returning an empty dictionary.")
            retval = SmartDict({})
        finally:
            return retval

    @staticmethod
    async def get_scope_headers(reader: asyncio.StreamReader)-> dict:
        headers = []
        dict_headers = SmartDict({})

        while True:
            header_line = await reader.readuntil(b"\r\n")
            header = header_line.rstrip()
            if not header:
                break
            key, value = header.split(b": ", 1)
            key = key.lower()
            headers.append([key, value])
            dict_headers[key.decode()] = value.decode()

        return headers, dict_headers        
    
    @staticmethod
    async def get_response_headers(scope: dict, event: dict)-> dict:
        http_version = scope.get("http_version")
        status = HTTPStatus(int(event.get("status")) or 404)
        status_line = f"HTTP/{http_version} {status.value} {status.phrase}\r\n"

        headers = [to_bytes(status_line)]
        for header_line in event.get("headers", []):
            # print(f"Header line: {header_line}")
            headers.append(b": ".join(map(to_bytes, header_line)))
            headers.append(b"\r\n")
        headers.append(f"Date: {time.strftime(strftime_template)}\r\n".encode('utf-8'))
        headers.append(f"server: TinA/{tina_version}\r\n".encode('utf-8'))
        headers.append(b"\r\n")

        # print(headers)
        return headers
    
    @staticmethod
    def is_request_line(request: str) -> bool:
        retval = False
        try:
            method, path, protocol = request.split(" ")
            if protocol.lower().startswith('http'):
                retval = True
            else:
                retval = False
        except:
            retval = False
        finally:
            # print(f"'{request}' is {'' if retval else 'NOT '}a valid request line. Returning {retval} from is_request_line.")
            return retval
        
    @staticmethod
    async def get_content_length(scope: dict)-> int:
        for [key, value] in scope["headers"]:
            if key == b"content-length":
                val = value.decode('utf-8') if type(value) == bytes else value
                return int(val)
        return 0        

    @staticmethod    
    async def demo_app(scope: dict, receive: Callable, send: Callable)-> None:
        return await demo_app(scope, receive, send)
    
    @staticmethod
    def get_default_style() -> str:
        return """
            <style>
                body {
                    font-family: sans-serif; 
                    font-size: 135%;
                    padding-left: 0.5em;
                }
                li {
                    list-style: circle;
                    margin-left: 1em;
                    margin-bottom: 0.5em;
                    padding-left: 0.5em;
                }
                a {
                    color: steelblue;
                    font-weight: bold;
                    text-decoration: none;
                }
                a:visited {
                    color: steelblue;
                }
                .green { color: #008000; }
                .grey {  color: grey; }
                .red { color: red; }
                .silver { color: silver; }
                .steelblue {color: steelblue; }
                .black {color: black; }

                .floatright {float: right;}
                .floatleft {float: left;}
                .centered {text-align: center; }
            </style>
        """

    @staticmethod
    def is_html(fragment):
        rtest1 = r'<(\w+)\s*.*>.*?</\1>'
        rtest2 = r'doctype\s*=?\s*html'
        to_be_tested = str(fragment).lower()
        return re.search(rtest1, to_be_tested) or re.search(rtest2, to_be_tested) or False

    @staticmethod
    def get_error_template() -> str:
        return """
        <html>
        <head><title>Error {}</title></head>
        <body style="font-family: sans-serif; font-size: 150%; padding-left: 0.5em;">
            <p style="text-align: center; font-size: 40px; margin-top: 1rem; margin-bottom: 0;">
                <span style="color: red;" class="code">{}</span>
                &nbsp;&nbsp;<span style="color: grey; class="url">{}</span>&nbsp;&nbsp;
                <span class="phrase">{}</span>
            </p>
            <hr>
            <p style="margin-bottom: 1rem; text-align: center; font-family: 'Times New Roman'; font-size: 16px;">TinA/{}</p>
            <hr>
            <p style="text-align: center;">
                <button onclick="history.back();">Back</button>
                <button onclick="location.href='/';">Home</button>
            </p>
        </body>
        </html>
        """
     
    @staticmethod
    # def get_request_header(scope: dict, key) -> str | bytes | None:
    def get_request_header(scope: dict, key):
        for [k, v] in scope.get('headers'):
            if to_bytes(k.lower()) == to_bytes(key.lower()):
                return v
        return None

    @staticmethod
    def rewrite_urls(key: str, payload) -> bytes:
        regex = r'(?P<tag>src|href|action)="(?P<url>.+?)"'
        payload = to_bytes(payload).decode('utf-8')
        payload_copy = payload
        start = 0
        m = True
        rewrites = []
        while m:
            m = re.search(regex, payload_copy[start:])
            if m:
                start += m.span()[1]
                url = m.groupdict().get('url')
                if url.startswith('http') or url.startswith('data'):
                    continue
                replacement = f"/{key}" if url.startswith("/") else f"/{key}/"
                orig = m.group()
                rewrites.append((orig, orig.replace(url, f"{replacement}{url}")))
        print('REWRITES: #\n', rewrites, '\n#\n')
        for orig, rewrite in rewrites:
            payload = payload.replace(orig, rewrite)
        return to_bytes(payload)

    @property
    def version(self):
        # TinaHandler.version = self.config.get('version')
        # return self.config.get('version')
        return tina_version
        
    @property
    def app(self) -> Callable:
        return self._app
    
    @app.setter
    def app(self, newApp: Callable)-> None:
        self._app = newApp
        if hasattr(self._app, 'handler'):
            self._app.handler = self

    @app.deleter
    def app(self)-> None:
        self.app = self.default_app

######################################################################################

async def static_app(scope: dict, receive: Callable, send: Callable, absolute_path= False)-> None:
    if len(TinaHandler.config.items()) == 0:
        TinaHandler.load_config()

    remote_host = scope.get('remote-host')
    # remote_ip = scope.get('x-real-ip')
    remote_ip = scope.get('client', ['unknown','unknown'])[0]
    method = scope.get('method').upper()
    pth = scope.get('path', '/')
    if pth.endswith("/") and len(pth) > 1:
        pth = pth[:-1]

    async def send_error(code, resource = None):
        statusobj = HTTPStatus(code)
        template = TinaHandler.get_error_template()
        resource = '' if resource is None else str(resource)
        body = template.format(statusobj.value, statusobj.value, resource, statusobj.phrase, tina_version)
        body_len = len(body)
        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {statusobj.value}")
        
        await send({
        "type": "http.response.start",
        "status": statusobj.value,
        "headers": [
                [b"content-type", b"text/html; charset=utf-8"],
                [b"content-length", str(body_len).encode('utf-8')],
            ],
            })
        
        return await send({
            "type": "http.response.body",
            "body": to_bytes(body),
            "more_body": False
        })

    async def send_redirection(where, code = 302):
        statusobj = HTTPStatus(code)
        if type(where) == str:
            where = where.encode('utf-8')

        await send({
        "type": "http.response.start",
        "status": statusobj.value,
        "headers": [(b"location", where)]
            })
        return await send({
            "type": "http.response.body",
            "body": b'',
            "more_body": False
        })

    async def send_proxy_pass(key, where):
        l = reduce(lambda r, item: [*r, item] if (item and item != key) else r, pth.split("/"), [])
        newpth = "/".join(l)
        # print(newpth)
        fullpath = "/".join((where, newpth))
        if len(scope.get('query_string')):
            fullpath += "?" + scope.get("query_string").decode('latin-1')
        parsed = urlparse(fullpath)
        query_string = f"?{parsed.query}" if len(parsed.query) else ''
        request_path = parsed.path + query_string 
        request_line = f"{scope.get('method').upper()} {request_path} {scope.get('scheme').upper()}/{scope.get('http_version')}\r\n"
        headers = ""
        for k, v in scope.get('headers'):
            header = f"{k.decode()}: {v.decode()}\r\n"
            # print(header)
            headers += header

        request = request_line + headers + "\r\n"

        request_body = b''
        if scope.get("method").lower() not in [b'get', b'head', b'options']:
            if len(scope.get('request_body')):
                request_body  = scope.get('request_body', b'') + b'\r\n'
            else:
                msg = await receive()
                request_body = msg.get('body') + b"\r\n"

        addrparts = parsed.netloc.split(":")
        addr, port = addrparts[0], "80" 
        if len(addrparts) > 1: 
            port = addrparts[1]
        addr = addr.strip()
        port = int(port.strip())

        pt_reader = None
        pt_writer = None
        try:
            pt_reader, pt_writer = await asyncio.open_connection(addr, port, limit = 65536 * 4)
            print(f"CONNECTION OPENED WITH {addr}:{port} AT {time.strftime(strftime_template)}")
        except:
            await send_error(404, pth)
            return 404

        try:
            pt_writer.write(to_bytes(request))
            await pt_writer.drain()
        except Exception as exc:
            print(f"Exception occurred while writing headers to proxy pass: '{exc}'")
            return await send_error(500, repr(exc))
        if len(request_body) > 2:
            try:
                pt_writer.write(request_body)
                await pt_writer.drain()
            except Exception as exc:
                print(f"Exception occurred while writing request body to proxy pass: '{exc}'")
                return await send_error(500, repr(exc))
        print(f"REQUEST SENT AT {time.strftime(strftime_template)}, AWAITING RESPONSE.")

        response_head = await pt_reader.readuntil(b'\r\n\r\n')
        print(f"GOT RESPONSE HEAD  AT {time.strftime(strftime_template)}")

        lines = response_head.split(b'\r\n')
        try: 
            # response_method_n_version, response_status, _ = lines[0].split(b" ")
            three_values_expected = lines[0].split(b" ")
            # response_status = int(response_status)
            response_status = int(three_values_expected[1])
            print(f"RESPONSE STATUS CODE: {response_status}")
        except Exception as exc:
            print(f"Error processing line: '{lines[0]}'")
            await send_error(500, repr(exc))
            return 500
        
        response_headers = []
        for line in lines[1:]:
            print(f"Processing response header line: '{line.decode()}'")
            if len(line):
                try:
                    k, v = line.split(b': ')
                    response_headers.append((k.lower(), v))
                except Exception as exc:
                    return await send_error(500, f"Error while processing line: '{line}': {exc}".encode('utf-8'))


        response_body = b''
        response_chunk = b''
        if response_status != 304:
            while True:
                response_chunk = await pt_reader.read()
                response_body += response_chunk
                if not len(response_chunk):
                    break
        print(f"GOT RESPONSE BODY AT {time.strftime(strftime_template)}")

        # print(response_headers)

        response_headers_dict = dict(response_headers)
        response_headers_dict[b'content-length'] = str(len(response_body)).encode('utf-8')

        response_content_type = response_headers_dict.get('content-type')
        if response_content_type and response_content_type.startswith(b'text/html'):
            print("It is HTML informed by response content-type header.")
            response_body = TinaHandler.rewrite_urls(key, response_body)
        elif response_content_type:
            print(f"It is {response_content_type}")
        else:
            if TinaHandler.is_html(response_body):
                print("It is HTML guessed examining contents")
                response_headers_dict[b'content-type'] = b'text/html; charset=utf-8'
                response_body = TinaHandler.rewrite_urls(key, response_body)
            else:
                guessed_type = guess_type(request_path)[0]
                if guessed_type:
                    response_headers_dict[b'content-type'] = guessed_type.encode('utf-8')
                    if guessed_type.startswith("text/html"):
                        response_headers_dict[b'content-type'] += b"; charset=utf-8"
                        print("It is HTML detected by guess_type")
                        response_body = TinaHandler.rewrite_urls(key, response_body)
                else:    
                    print("Shit! We don't know what it is, and we should, in order to provide 'rewrite_urls' in case it's HTML.")
                    response_body = TinaHandler.rewrite_urls(key, response_body)

        response_headers = response_headers_dict.items()
        print(f"RESPONSE HEADERS:\n{response_headers}")

        await send({
        "type": "http.response.start",
        "status": response_status,
        "headers": response_headers
            })
        
        await send({
            "type": "http.response.body",
            # "body": pt_response,
            "body": response_body,
            "more_body": False
        })

        return response_status

    async def send_mp4(filepath):
        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")

        def getrange(rangebytes: bytes) -> tuple[int, int]:
            # with open(f"log/ranges.log", "ba") as fd:
            #     fd.write(to_bytes(pth) + b" (" + time.strftime("%X").encode() + b"): " + rangebytes + b'\n')
            _, points = rangebytes.split(b"=")
            if b"," in points:
                print(f"\n@Range requested@\n{points}\n@@@\n")
            begin, end = points.split(b"-")
            try:
                b = int(begin)
                e = int(end) if len(end) else 0
            except:
                b, e = 0, 0
            return b, e
        
        mp4 = Mp4(filepath)
        status_code = 200
        received, begin, end = 0, 0, mp4.filesize
        response_headers = TinaHandler.common_response_headers() + TinaHandler.resource_response_headers(filepath)
        bytez = TinaHandler.get_request_header(scope, b"range")
        if bytez:
            begin, end = getrange(bytez)
            end = (mp4.filesize - 1) if not end else end
            response_headers.append([b"content-range",  f"bytes {begin}-{end}/{mp4.filesize}".encode('utf-8')])
            for h in response_headers:
                if h[0] == 'content-length':
                    h[1] = str(end - begin + 1).encode('utf-8')
                    break
            status_code = 206

        stream = mp4.stream_range(begin, end)

        startdict = SmartDict(type='http.response.start', status=status_code, headers=response_headers)
        try:        
            await send(startdict)
            await send(SmartDict(type='http.response.body', body=b'', more_body=True))
            for chunk in stream:
                bodydict = SmartDict(type='http.response.body', body=chunk, more_body=True)
                await send(bodydict)
        except Exception as exc:
            print(f"Exception occurred while streaming mp4 content to client: {exc}")
        finally:
            try:
                bodydict = SmartDict(type='http.response.body', body=b'', more_body=False)
                await send(bodydict)
            except:
                pass
            print("Video stream closed.")
            return

    async def send_chunked_file(filepath):
        ftype = guess_type(filepath)
        ftype = ftype[0] if ftype and ftype[0] else "application/x-trash"
        if ftype.startswith("text"):
            ftype += "; charset=utf-8"

        def can_gzip()-> bool:
            retval: bool = not ftype.startswith('video')
            retval = retval and not ftype.endswith('jpg')
            retval = retval and not ftype.endswith('jpeg')
            ae = TinaHandler.get_request_header(scope, b'accept-encoding')
            ag = False if not ae else ae.find(b'gzip') != -1
            # ae and print(f"Request accepts encoding: {ae.decode('utf-8')}")
            retval = retval and ag

            return retval
            # return False

        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")

        if ftype in ["video/mp4", "video/quicktime"]:
            return await send_mp4(filepath)

        ### Added 21/06/2024
        body = b''
        file_stat = os.stat(filepath)
        body_len = file_stat.st_size
        # body = b''

        file_desc = open(filepath, "rb")
        if can_gzip():
            body = gzip.compress(file_desc.read())    
            body_len = len(body)
            body = io.BytesIO(body)
        else:
            body = file_desc

        chunks, tail = TinaHandler.chunks(body_len)
        response_headers = [
                    [b"content-type", to_bytes(ftype)],
                    [b"content-length", str(body_len).encode('utf-8')],
                    [b'transfer-encoding', b'chunked']
                ]
        if can_gzip():
            response_headers = [*response_headers, [b"content-encoding",  b"gzip"]]
        if ftype.startswith('video') or ftype.startswith('audio'):
            # response_headers = [*response_headers, [b"accept-ranges",  b"bytes"], [b"connection", b"keep-alive"]]
            response_headers = [*response_headers, *TinaHandler.common_response_headers()]

        ranges = TinaHandler.get_request_header(scope, b"range")
        if ranges:
            stri = f"Ranges requested: {ranges.decode('utf-8')}"
            with open("log/file_log.txt", "a") as logfile:
                logfile.writelines([stri + '\n'])
            print(stri)

        try:
            await send({
            "type": "http.response.start",
            "status": 200,
            "headers": response_headers,
            })

            if len(chunks):
                chunk_size = TinaHandler.config.get("chunk-size")
                for index, chunk in enumerate(chunks):
                    # print(f"Sending chunk number {index + 1} ({chunk[0]}-{chunk[1]}) of {len(chunks)}")
                    print(".", end="")
                    await send({
                        "type": "http.response.body",
                        # "body": body[chunk[0]:chunk[1]],
                        "body": hex(chunk_size).lstrip('0x').encode('utf-8') + b"\r\n" + body.read(chunk_size) + b"\r\n",
                        # "body": body.read(chunk_size)
                        "more_body": True
                    })
            if tail:
                print(f"\nSending last chunk (tail) ({tail[0]}-{tail[1]}) for file {scope.get('path')}")
                tail_bytes = body.read()
                tail_len = len(tail_bytes)
                await send({
                    "type": "http.response.body",
                    # "body": body[tail[0]:tail[1]] if tail else b'',
                    "body": hex(tail_len).lstrip('0x').encode('utf-8') + b"\r\n" + tail_bytes + b"\r\n",
                    # "body": tail_bytes,
                    "more_body": True
                })
            else:
                print(f"Closing transmission for file {scope.get('path')} with no further data.")
            
            await send({
                "type": "http.response.body",
                # "body": b'',
                "body": b'0\r\n' + b'' + b'\r\n',
                # "body": b'0\r\n',
                "more_body": False
            })

        except BrokenPipeError as bpErr:
            print(f"Broken pipe ({errno.EPIPE}). Leaving intent of sending {scope.get('path')}.")
            return
        except Exception as exc:
            print(f"Exception ({exc}). Leaving intent of sending {scope.get('path')}.")
            return

    async def send_file(filepath):
        ftype = guess_type(filepath)
        ftype = ftype[0] if ftype and ftype[0] else "application/x-trash"
        if ftype.startswith("text"):
            ftype += "; charset=utf-8"

        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")

        if ftype in ["video/mp4", "video/quicktime"]:
            return await send_mp4(filepath)

        body = b''

        def file_data():
            # file_desc = open(filepath, "rb")
            # file_stat = os.stat(filepath)
            file_desc = os.open(filepath, os.O_RDONLY | os.O_NONBLOCK)
            file_stat = os.fstat(file_desc)
            body_len = file_stat.st_size
            return body_len, file_desc
        
        body_len, file_desc = await asyncio.to_thread(file_data)

        response_headers = [
                    [b"content-type", to_bytes(ftype)],
                    [b"content-length", str(body_len).encode('utf-8')]
                ]
        if ftype.startswith('video') or ftype.startswith('audio'):
            response_headers = [*response_headers, *TinaHandler.common_response_headers()]

        try:
            await send({
            "type": "http.response.start",
            "status": 200,
            "headers": response_headers,
            })

            chunk_size = TinaHandler.config.get('chunk-size', 8192)
            # chunk_size = 8192
            remaining = body_len

            while remaining > 0:
                try:
                    part = os.read(file_desc, min(remaining, chunk_size))
                    if not part:
                        # raise RuntimeError(f"Something was wrong while reading {scope.get('path')}") 
                        break
                    remaining -= len(part)
                    if not remaining:
                        pass
                        #print(f"Finished reading {scope.get('path', '---')}")
                    await send({
                        "type": "http.response.body",
                        "body": part, 
                        "more_body": True
                    })
                except BlockingIOError as e:
                    if e.errno == errno.EAGAIN:
                        # No data available *right now*, try again later
                        # print("No data ready yet, try again")
                        await asyncio.sleep(0)
                        continue
                    else:
                        os.close(file_desc)
                        raise                

            await send({
                "type": "http.response.body",
                "body": b'',
                "more_body": False
            })

        except BrokenPipeError as bpErr:
            print(f"Broken pipe ({errno.EPIPE}). Leaving intent of sending {scope.get('path')}.")
            return
        except Exception as exc:
            print(f"Exception ({exc}). Leaving intent of sending {scope.get('path')}.")
            return
        finally:
            try:
                os.close(file_desc)
            except Exception as exc:
                pass
                #print(f"Exception while closing file descriptor for {scope.get('path')}: {exc}")
            # print("File transmission closed.")
            
    async def send_directory(path, dirpath):
        if not TinaHandler.config.get('dirlisting-enabled'):
            return await send_error(403)
        
        def get_file_details(entry):
            fullpath = dirpath + os.path.sep + entry
            size = os.path.getsize(fullpath)
            ret = f'<span>&nbsp;</span><span style="margin-left: 3em; margin-right: 8em; text-align: right;" class="black floatright">{size:,} bytes.</span>'
            return ret
        
        prevdir = os.path.split(path)[0]
        body = f"""
            <!DOCTYPE html>
            <html><head><title>Directory Listing</title>
            {TinaHandler.get_default_style()}
            </head><body style="margin-left: 1em; margin-right: 1em;">
            <h2>Directory listing for <span class="green">.{path}</span></h2></hr>
            <hr>
            <p style="margin-bottom: 1em; text-align: center; font-family: Times New Roman; font-size: 16px;">TinA/{tina_version}</p>
            <hr>
            <ul>
                <li><a title="Home" href="/">.</a></li>
                <li><a title="{prevdir}" href="{prevdir}">..</a></li>
        """
        entries = os.listdir(dirpath)
        entries.sort()
        entries.sort(key=lambda e: os.path.isdir(dirpath + os.path.sep + e), reverse=True)
        for entry in entries:
            body += f'''
            <li>
                <a href="{path + (os.path.sep if path != '/' else '') + entry}">{entry}&nbsp;
                {'<span class="silver">[DIR]</span>' if (await asyncio.to_thread(os.path.isdir, dirpath + os.path.sep + entry)) else get_file_details(entry)}</a>
            </li>'''
        body += "</ul></body></html>"
        body_len = len(body)
        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")
        
        await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
                [b"content-type", b"text/html; charset=utf-8"],
                [b"content-length", str(body_len).encode('utf-8')],
            ],
            })
        
        return await send({
            "type": "http.response.body",
            "body": to_bytes(body),
            "more_body": False
        })
    
    async def send_cgi(cgipath):
        async def actually_send_cgi():
            environ = {}
            environ['GATEWAY_INTERFACE'] = f'CGI/{scope.get("http_version")}'
            environ['SERVER_SOFTWARE'] = scope.get("server_software")
            environ['REQUEST_METHOD'] = scope.get("method", "GET").upper()
            environ['CONTENT_LENGTH'] =  str(len(request_body))
            environ['SERVER_NAME'] = scope.get('server_name')
            environ['SERVER_PORT'] = scope.get('local_port')
            environ['REMOTE_HOST'] = scope.get('remote-host')
            environ['REMOTE_PORT'] = scope.get('remote-port')
            environ['QUERY_STRING'] = scope.get('query_string', b'').decode('utf-8')
            environ['CGI_PATH'] = scope.get('path')
            environ['SCRIPT'] = os.path.split(scope.get('path', ''))[1]
            environ['X-REAL-IP'] = scope.get('x-real-ip', '127.0.0.1')

            for [k, v] in scope.get("headers", []):
                key = k.decode('utf-8').upper().replace('-', '_')
                if key == 'CONTENT_TYPE':
                    environ['CONTENT_TYPE'] = v.decode('utf-8')
                #print(f"Setting HTTP_{key} to {v.decode('utf-8')}")
                environ[f'HTTP_{key}'] = v.decode('utf-8')

            pipe = asyncio.subprocess.PIPE
            process = await asyncio.create_subprocess_exec(cgipath, stdin=pipe, stdout=pipe, stderr=pipe, env=environ)
            out, _ = await process.communicate(request_body)
            io_out = io.BytesIO(out)
            resp_line = io_out.readline()
            io_out.seek(0)
            resp_line = resp_line.strip(b'\r\n')
            code = b'404'
            try:
                _, code, phrase = resp_line.split(b' ', 3)
            except:
                pass
            # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {code.decode('utf-8')}")
            writer = scope.get('_writer')
            if not writer:
                raise RuntimeError("No writer socket to send response.")
            writer.write(out)
            try: 
                await writer.drain()
            except Exception as exc:
                print(f"Exception occurred while trying to send CGI data to remote host: '{exc}'")
                return await send_error(500, repr(exc))
            finally:
                try: 
                    writer.close()
                    await writer.wait_closed()
                except:
                    print(f"Exception occurred while trying to close pipe to remote host for CGI data: '{exc}'")
                    return await send_error(500, repr(exc))

# 
        if TinaHandler.config.get('cgi-enabled'):
            if await asyncio.to_thread(os.path.isfile, cgipath): 
                if await asyncio.to_thread(os.access, cgipath, os.X_OK):
                    return await actually_send_cgi()
                else:
                    # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
                    return await send_error(403, os.path.split(cgipath)[1])
            else:
                # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
                return await send_error(403,  os.path.split(cgipath)[1])
        else:
            # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
            return await send_error(403,  os.path.split(cgipath)[1])

    body = ""     
    static_dir = TinaHandler.config.get('static-dir', 'static')
    if not static_dir or (not os.path.exists(static_dir)) or absolute_path:
        # static_dir = os.path.split(os.getcwd())[1]
        static_dir = "."
    # print(f"static directory is: {static_dir}")
    cgi_dir = TinaHandler.config.get('cgi-dir')
    # print(f"CGI directory is: {cgi_dir}")
    pth = scope.get('path', '/') if scope else ''
    # print(f"Requested path is: {pth}")
    fullpath = ""
    is_cgi = False 



    if TinaHandler.config.get('redirects') and pth[1:] in TinaHandler.config.get('redirects').keys():
        d = TinaHandler.config.get('redirects')
        where = d.get(pth[1:])
        # print(f"(PID {os.getpid()}) \nRedirect {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 302")
        return await send_redirection(where)

#    if pth[1:] in TinaHandler.config.get('proxy_pass').keys():
    for key in TinaHandler.config.get('proxy_pass').keys():
        if pth[1:].startswith(key):
            d = TinaHandler.config.get('proxy_pass')
            # where = d.get(pth[1:])
            where = d.get(key)
            retcode = await send_proxy_pass(key, where)
            # print(f"\n(PID {os.getpid()}) Proxy pass {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {retcode}")
            return 
    
    if pth in easter_eggs.keys() and scope.get('method').lower().strip() == 'get':
        body = TinaHandler.get_default_style() + '<div>'
        body += easter_eggs[pth].replace("\n", "<br/>") + "</div><p>&nbsp;</p>\r\n"
        body_len = len(body)

        await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
                [b"content-type", b"text/html; charset=utf-8"],
                [b"content-length", str(body_len).encode('utf-8')],
            ],
            })
        
        return await send({
            "type": "http.response.body",
            "body": to_bytes(body),
            "more_body": False
        })

    if pth == '/demo':
        try:
            return await demo_app(scope, receive, send)
        except Exception as exc:
            _, _, trace_back = os.sys.exc_info()
            lineno = trace_back.tb_lineno
            print(f"Exception occurred while trying to load demo app at line {lineno}: '{exc}'\nTraceback: {repr(trace_back)}")

    if pth == '/uploader':
        try:
            from formhandler import formhandler
            return await formhandler(scope, receive, send)
        except Exception as exc:
            _, _, trace_back = os.sys.exc_info()
            lineno = trace_back.tb_lineno
            print(f"Exception occurred while trying to load formhandler at line {lineno}: '{exc}'\nTraceback: {repr(trace_back)}")


    fullpath = f"{os.path.abspath(static_dir)}{pth}"
    is_cgi = False
    m = re.match(f".*{cgi_dir}.*", pth)
    # print(f"CGI string in position in path is: {m}")
    if m:
        is_cgi = True
        # print(f"CGI request detected for path: {pth}, full CGI path is: {fullpath}")
    else:
        is_cgi = False
        # print(f"{pth} NOT a CGI request. Full path is: {fullpath}")
    # print(f"Full path is: '{fullpath}' and it is {'' if is_cgi else 'not '}CGI content.")


    if pth == '/':
        candidates = ['index.html', 'index.htm']
        for candidate in candidates:
            if await asyncio.to_thread(os.path.exists, f"{fullpath}{candidate}"):
                fullpath += candidate
                # print(f"Real fullpath: {fullpath}")
                break

    requires_body: bool = scope.get('method', 'get').lower() if scope else 'get' in ['post', 'put', 'patch']
    # requires_body and print("\nThis request needs to receive body.")
    request_body = b''
    if requires_body:
        msg = await receive()
        request_body = msg.get('body')

    # Keep this just in case...    
    # form = TinaHandler.form(scope or {}, request_body)

    # len(request_body) and print(f"Request body: '{request_body.decode('latin-1')}'")

    fexists: bool = await asyncio.to_thread(os.path.exists, unquote(fullpath))
    if fexists:
        # print(f"{fullpath} EXISTS! and it is {'' if is_cgi else 'not '}CGI content.")
        if not is_cgi:
            if await asyncio.to_thread(os.path.isdir, unquote(fullpath)):
                # print(f"Serving directory: {pth}")
                return await send_directory(pth, unquote(fullpath))
            elif await asyncio.to_thread(os.path.isfile, unquote(fullpath)):
                # print(f"Serving file: {pth}")
                return await send_file(unquote(fullpath))
        else:
            # print(f"Serving CGI: {pth}")
            return await send_cgi(unquote(fullpath))
    else:
        # print(f"{fullpath} doesn't exist.")
        return await send_error(404, pth)

async def demo_app(scope, receive: Callable, send: Callable)-> None:
    visitors = await get_visitors()

    proc_name = multiprocessing.current_process().name
    thread_name = threading.current_thread().name
    thread_count = threading.active_count()
    scope = scope.copy() if scope else {}
    # for to_exclude in ['_wsgi_environ', '_reader', '_writer', '_sock', '_server.dict_headers']:
    for to_exclude in ['_reader', '_writer', '_sock', '_server.dict_headers']:
        if scope.get(to_exclude):
            del scope[to_exclude]
    method = scope.get('method').lower() if scope.get('method') else 'get'
    request = await receive()
    req_body = request.get('body') if method not in ['get', 'head', 'options'] else b''
    info = f"""(PID {os.getpid()} - {proc_name}/{thread_name} of {thread_count - 1}) {method.upper()} {scope.get('path')} requested by {scope.get('x-real-ip')}
    at {time.strftime('%Y-%m-%d %H:%M:%S')} - 200 
    """.replace('\n', ' ')
    # print(info)
    if  len(req_body): 
        print(f"Request body length: {len(req_body)}")
    
    body = "<style> body { font-family: sans-serif;}\n .tspan {color: steelblue;}</style>"
    body += '<div style="text-align: center;"><img src="/img/tina.png" style="border-radius: 15px;"/></div><hr>'
    body += f"<h1>Welcome to Tiny Asynchoronous Web Server - (TinA) version {tina_version}</h1>\t"
    if scope.get('path') != '/favicon.ico':
        visitors += 1
        await set_visitors(visitors)
    body +=f"""
    <hr/><p>You're visitor No {visitors}   ({proc_name}/{thread_name} of {thread_count - 1})   
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<button onclick="location.href = location.href;">Reload</button>
    </p><hr/>\n<h3>Scope Vars</h3>
    """
    for k in scope:
        if k not in ['headers', '_wsgi_environ']:
            body += f"<p><span class='tspan'>{k}</span> = {scope.get(k)}</p>\n"
    body +="<hr/><h3>Request Headers</h3>\n"
    headers = scope.get('headers')
    for [k, v] in headers:
        body += f"<p><span class='tspan'>{k.decode('utf-8')}</span> = {v.decode('utf-8')}</p>\n"
    body +="<hr/><h3>WSGI Environment</h3>\n"
    wsgi_env = scope.get('_wsgi_environ', {})
    # body += f"<p><span class='tspan'>wsgi_environ</span> = {wsgi_env}</p>\n"
    for k in wsgi_env:
        body += f"<p><span class='tspan'>{k}</span> = {wsgi_env[k]}</p>\n"
    body +="<hr/>\n"
    body +="""<button onclick="location.href = '/';">HOME</button>"""
    if len(req_body):
        body += f"<hr/><p>{repr(req_body)}</p>\n"
    body = to_bytes(body)
    body_len = len(body)

    await send({
    "type": "http.response.start",
    "status": 200,
    "headers": [
            [b"content-type", b"text/html; charset=utf-8"],
            [b"content-length", str(body_len).encode('utf-8')],
        ],
        })
    await send({
        "type": "http.response.body",
        "body": body,
        "more_body": False
    })

######################################################################################

def main_sigint_handler():
    print(f"\nServer process {os.getpid()} exiting...\nBye, bye!\n")
    os.sys.exit(0)

######################################################################################

def loop_sigint_handler(loop, signl):
    if signl == signal.SIGINT:
        try:
            loop.stop()
            loop.close()
        except Exception as exc:
            pass
        finally:
            print(f"\nServer process {os.getpid()} exiting...\nBye, bye!\n")
            os.sys.exit(0)

######################################################################################

def loop_sigusr_handler(loop, signl):
    if signl == signal.SIGUSR1:
        try:
            loop.stop()
            loop.close()
        except Exception as exception:
            pass
        finally:
            print(f"\nReceived USR1 signal.\nRestarting...\n")
            time.sleep(0.5)
            os.execv(os.sys.executable, ['python3'] + os.sys.argv)

######################################################################################

def fs_monitor():
    def get_file_hash(file):
        fd = open(file, 'rb')
        if not fd:
            print(f"Error opening file '{file}' for hash calculation.")
            return None
        filebytes = fd.read()
        fd.close()
        if not filebytes:
            print(f"Error reading file '{file}' for hash calculation.")
            return None
        return hashlib.sha1(filebytes).hexdigest()

    files = {}
    # dirlist = os.listdir(os.path.split(__file__)[0])
    dirlist = os.listdir(os.getcwd())
    for entry in dirlist:
        suffix = os.path.splitext(entry)[1]
        if suffix in ['.py', '.json']:
            files[entry] = get_file_hash(entry)

    # print(f"Watching {len(files)} files for changes.")

    while True:
        time.sleep(1)
        for k in files.keys():
            if os.path.exists(k):
                if get_file_hash(k) != files[k]:
                    print(f"File '{k}' has changed. Signaling server restart")
                    os.kill(os.getpid(), signal.SIGUSR1)
                    return
            else:
                print(f"File '{k}' has been deleted. Signaling server restart")
                os.kill(os.getpid(), signal.SIGUSR1)
                return
            
######################################################################################

async def runner(server):
    await server.serve_forever()

######################################################################################

async def run_dev_server(app: Callable = None, host: str = '', port: int = tina_port):
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, loop_sigint_handler, loop, signal.SIGINT)
        loop.add_signal_handler(signal.SIGUSR1, loop_sigusr_handler, loop, signal.SIGUSR1)
    except Exception as exc:
        print(f"Exception ocurred while trying to set loop signal handler: {exc}")

    server = await asyncio.start_server(TinaHandler(app or static_app), host, port, reuse_address=True, reuse_port=True)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    banner = f'''
TinA {server.__class__.__name__} v. {tina_version} (PID {os.getpid()}) serving HTTP on {addrs}
    '''
    print(f"{banner}\n{'-' * len(banner)}\n")

    # asyncio.create_task(asyncio.to_thread(fs_monitor))
    monitor = threading.Thread(target=fs_monitor, daemon=True)
    monitor.start()
    # monitor.join()
    await server.serve_forever()

######################################################################################

async def run_server(app: Callable = None, host: str = '', port: int = tina_port, *, 
                     limit= 65536, multiprocess:bool = False, num_processes:int = None,
                     multithread:bool = True, num_threads:int = None):

    loop = asyncio.get_running_loop()

    try:
        signal.signal(signal.SIGINT, main_sigint_handler)
    except Exception as exc:
        print(f"Exception ocurred while trying to set main signal handler: {exc}")

    try:
        loop.add_signal_handler(signal.SIGINT, loop_sigint_handler, loop, signal.SIGINT)
    except Exception as exc:
        print(f"Exception ocurred while trying to set loop signal handler: {exc}")

    num_processes = os.cpu_count() if not num_processes else num_processes
    num_threads = num_processes * 4 if not num_threads else num_threads
    if not multiprocess:
        num_processes = 1
    if not multithread:
        num_threads = 1

    handler = None

    if app is None:
        handler = TinaHandler.static()
    else:
        handler = TinaHandler(app)
        #app.handler = handler

    async def runner():
        server = await asyncio.start_server(handler, host="0.0.0.0", port=tina_port, limit=limit, reuse_address=True, reuse_port=True)
        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        banner = f'''
        TinA {server.__class__.__name__} v. {tina_version} (PID {os.getpid()}) serving HTTP on {addrs} - Processes: {num_processes or 1} - Threads: {num_threads}
    '''
        print(f"{banner}\n{'-' * len(banner)}\n")
        await server.serve_forever()
    
    # await asyncio.gather(*[asyncio.to_thread(await runner()) for _ in range(num_threads)])
    # await asyncio.gather(*[asyncio.create_task(asyncio.to_thread(await server.serve_forever())) for _ in range(num_threads)])
    #await asyncio.gather(*[asyncio.to_thread(await server.serve_forever()) for _ in range(num_threads)])

    def run(lp):
        asyncio.set_event_loop(lp)
        asyncio.run(runner())
    
    threads = []
    for i in range(num_threads):
        threads.append(threading.Thread(target=run, args=(loop, ), name=f"Server-Thread-{str(i + 1).zfill(3)}", daemon=True))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

######################################################################################
       
default_host = '0.0.0.0'
default_port = tina_port

######################################################################################

def start_running():
    host = (len(os.sys.argv) > 1 and os.sys.argv[1]) or default_host
    port = (len(os.sys.argv) > 2 and os.sys.argv[2]) or default_port
    port = int(port)
    App = None
    if len(os.sys.argv) > 3:
         if os.sys.argv[3].lower() == 'echo':
            App = handle_echo
         elif os.sys.argv[3].lower() == 'tinademo':
            App = TinaHandler.demo_app
         else:
            App = None
    asyncio.run(run_dev_server(App, host, port))

######################################################################################

def main():
    os.system("clear")
    visitors: int = asyncio.run(get_visitors())
    print(f"Opening server. Currently {visitors} visitors.\n")
    try:
        start_running()
    except KeyboardInterrupt:
        print()
        print("Tina server shutting down.\nBye for now...")
        os.sys.exit(0)
    except Exception as exc:
        print(f"ERROR: {exc} Trying to restore...")
        main()
        # os.sys.exit(-1)

######################################################################################

if __name__ == '__main__':
    main()
