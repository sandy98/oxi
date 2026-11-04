#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# master_worker.py
import socket, struct, asyncio, os, sys, subprocess, json, importlib
import inspect, io, hashlib, base64, logging, signal
from urllib.parse import urlparse, unquote
from http import HTTPStatus
from time import strftime
from typing import Callable
from pathlib import Path
from email.utils import formatdate

if __name__ == "__main__" and not __package__:
    __package__ = "oxi"
    
uvloop_available:bool = False

# Reset code (turns off all styling)
RESET = '\033[0m'

# Foreground standard colors
BLACK   = '\033[30m'
RED     = '\033[31m'
GREEN   = '\033[32m'
YELLOW  = '\033[33m'
BLUE    = '\033[34m'
MAGENTA = '\033[35m'
CYAN    = '\033[36m'
WHITE   = '\033[37m'

async def log_msg(msg:str, fp=sys.stdout):
    wmsg = f"{msg}\n"
    fp.write(wmsg)
    fp.flush()

filepath = Path(__file__)
# print(str(filepath))
parentpath = filepath.parent
# print(str(parentpath))
grandparentpath = parentpath.parent
# print(str(grandparentpath))
examples_virtual_env_path = f"{parentpath}{os.path.sep}apps{os.path.sep}.examples-virtual-env/lib/python3.10/site-packages"
options_virtual_env_path = f"{parentpath}{os.path.sep}.options-virtual-env/lib/python3.10/site-packages"

if Path(examples_virtual_env_path).is_dir():
    sys.path.insert(0, str(examples_virtual_env_path))
if Path(options_virtual_env_path).is_dir():
    sys.path.insert(0, str(options_virtual_env_path))

try:
    import uvloop # pyright: ignore[reportMissingImports]
    uvloop.install()
    # if uvloop_available == False:
    #     print(f"{CYAN}[Python Worker]{RESET} Asyncio using Uvloop.")
    uvloop_available = True
except ImportError:
    uvloop_available = False
    # print(f"{CYAN}[Python Worker]{RESET} Uvloop not available.")

sys.path.insert(0, str(parentpath))
sys.path.insert(0, str(grandparentpath))

__package__ = "oxi"

try:
    from __about__ import __version__ as version
    from __about__ import __config__ as config
    from utils import to_bytes #, bytes_to_human_readable
except Exception as exc:
    excname = exc.__class__.__name__
    print(f"{excname} exception: {exc}")
    raise

VERSION = version
CONFIG = config

# 🚀 WebSocket Hardening: Maximum allowed size for a single frame's payload.
# Prevents OOM attacks via malicious payload_len headers.
MAX_WS_PAYLOAD = 1 * 1024 * 1024  # 1 MiB

class SuppressBrokenPipeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Intercept the specific asyncio write warnings
        if record.name == "asyncio" and "socket.send() raised exception" in record.getMessage():
            return False  # Drop the log completely
        return True

# Apply the filter to the standard asyncio logger
asyncio_logger = logging.getLogger("asyncio")
asyncio_logger.addFilter(SuppressBrokenPipeFilter())

enctypes:tuple = (b"application/x-www-form-urlencoded", 
                   b"multipart/form-data", 
                   b"application/json",
                   b"text/plain")

strftime_template:str = "%a, %d  %b %Y %X %Z"

# global reference holder inside server.py
_embedded_global_loop = None

_lifespan_ready = False

class LifespanStartupError(Exception):
    """Raised when an ASGI app fails to complete its lifespan startup."""
    pass

def get_rfc_date() -> str:
    """
    Returns an HTTP header date in RFC 7231 format (GMT).
    Example: 'Tue, 27 Oct 2026 14:00:22 GMT'
    """
    return formatdate(timeval=None, localtime=False, usegmt=True)

def parse_http_stream(read_line_func) -> dict:
    """
    Parser HTTP unificado y genérico. 
    Recibe una función de lectura de línea para independizarse del tipo de transporte.
    """
    global version

    try:
        initial_line_bytes = read_line_func()
        if not initial_line_bytes:
            return {}
                 
        initial_line = to_bytes(initial_line_bytes).decode('latin-1').strip()
        parts = initial_line.split(" ")
        if len(parts) < 3:
            return {}
            
        method, complete_uri, protocol = parts[0], parts[1], parts[2]
        
        raw_path = complete_uri
        query_string = ""
        if "?" in complete_uri:
            raw_path, query_string = complete_uri.split("?", 1)
            
        path_decoded = unquote(raw_path)
        
        headers = {}
        while True:
            line_bytes = read_line_func()
            line = to_bytes(line_bytes).decode('latin-1').strip()
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
                
        return {
            "version": version,
            "method": method,
            "path": path_decoded,
            "raw_path": raw_path,
            "query_string": query_string,
            "protocol": protocol,
            "headers": headers
        }
    except Exception:
        return {}

def parse_http_raw_text(raw_text: str) -> dict:
    """
    El único y verdadero micro-parser HTTP de la Suite Oxi.
    Procesa un bloque de texto crudo y genera el diccionario request estandarizado.
    """
    global version
    try:
        lines = raw_text.splitlines()
        if not lines:
            return {}
            
        initial_line = lines[0].strip()
        parts = initial_line.split(" ")
        if len(parts) < 3:
            return {}
            
        method, complete_uri, protocol = parts[0], parts[1], parts[2]
        
        raw_path = complete_uri
        query_string = ""
        if "?" in complete_uri:
            raw_path, query_string = complete_uri.split("?", 1)
            
        path_decoded = unquote(raw_path)
        
        headers = {}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
                
        return {
            "version": version,
            "method": method,
            "path": path_decoded,
            "raw_path": raw_path,
            "query_string": query_string,
            "protocol": protocol,
            "headers": headers
        }
    except Exception:
        return {}

async def parse_standalone_request(reader: asyncio.StreamReader) -> dict:
    try:
        # Native, atomic read optimized by asyncio's C-level buffers.
        # It guarantees the entire HTTP header block is captured up to the blank line boundary.
        raw_buffer = await reader.readuntil(b'\r\n\r\n')
        
        if not raw_buffer:
            return {}
            
        return parse_http_raw_text(to_bytes(raw_buffer).decode('latin-1'))
    except asyncio.IncompleteReadError as e:
        # Handles edge cases where the client drops the connection prematurely
        if e.partial:
            return parse_http_raw_text(to_bytes(e.partial).decode('latin-1'))
        return {}
    except Exception:
        return {}

async def log_access(scope: dict, status_code: int, bytes_sent: int):
    """
    Generates and flushes an upstream access log matching Nginx compliance structure:
    181.199.145.251 - - [31/Aug/2026:17:02:19 -0300] "GET /favicon.ico HTTP/1.1" 200 76678
    """
    # Extraer IP remota (la IP del cliente real procesada en get_scope)
    client_tuple = scope.get("client", (b"127.0.0.1", 0))
    remote_addr = to_bytes(client_tuple[0]).decode('latin-1').rjust(15) if isinstance(client_tuple, (list, tuple)) else "127.0.0.1".rjust(15)
    
    # Reconstruir la línea de petición HTTP original
    method = scope.get("method", "GET").upper()
    path = scope.get("path", "/")
    
    # Si hay query string, la concatenamos para que salga idéntico en el request path
    query_string = to_bytes(scope.get("query_string", b"")).decode('latin-1')
    full_path = f"{path}?{query_string}" if query_string else path
    
    http_version = scope.get("http_version", "1.1")
    request_line = f'{method} {full_path} HTTP/{http_version}'
    
    # Ensamblar la cadena final estilo Nginx
    nginx_log_line = f'{CYAN}{remote_addr}{RESET} - - [{get_styled_date()}] "{request_line}" {status_code} {bytes_sent}'
    
    # Escribir al canal de logs del sistema de forma asíncrona
    await log_msg(nginx_log_line)

def is_websocket_upgrade(request):
    has_upgrade_ws = False
    has_connection_upgrade = False
    
    for (k, v) in request.get("headers", {}).items():
        k_low = k.lower()
        v_low = v.lower()
        
        # The connection header can contain multiple tokens like "keep-alive, Upgrade"
        if k_low == "upgrade" and v_low == "websocket":
            has_upgrade_ws = True
        elif k_low == "connection" and "upgrade" in v_low:
            has_connection_upgrade = True
        
    return has_upgrade_ws and has_connection_upgrade

def is_wsgi(callable_app) -> bool:
    """
    Ernesto's deterministic signature inspector for classical WSGI contracts.
    """
    if not callable_app:
        return False
    if not callable(callable_app):
        return False
    try:
        params = list(inspect.signature(callable_app).parameters.items())
        if len(params) != 2:
            return False
        return params[0][0].lower() == "environ" and params[1][0].lower() == "start_response"
    except Exception:
        return False

def scope_to_environ(scope: dict, body_bytes: bytes) -> dict:
    """
    Translates an ASGI metadata scope dictionary into a standard WSGI PEP 3333 environ.
    """
    headers = scope.get("headers", [])
    headers_dict = {to_bytes(k).decode('latin-1').lower(): to_bytes(v).decode('latin-1') for k, v in headers}
    
    # Reconstruct the query string parameter block
    query_bytes = to_bytes(scope.get("query_string", b""))
    query_string = query_bytes.decode('latin-1')

    environ = {
        "REQUEST_METHOD": scope.get("method", "GET").upper(),
        "SCRIPT_NAME": "",
        "PATH_INFO": scope.get("path", "/"),
        "QUERY_STRING": query_string,
        "SERVER_NAME": scope.get("server_name", f"OxiServer/{scope.get('oxi_version', '0.0.1')}"),
        "SERVER_PORT": str(scope.get("server", ["localhost", 8000])[1]),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": scope.get("scheme", "http"),
        "wsgi.input": io.BytesIO(body_bytes),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_forever": True,
        "CONTENT_LENGTH": str(len(body_bytes)),
        "CONTENT_TYPE": headers_dict.get("content-type", "")
    }

    # Map dynamic incoming HTTP headers with the WSGI HTTP_ prefix
    for k, v in headers_dict.items():
        if k not in ["content-type", "content-length"]:
            # env_key = "HTTP_" * uppercase(replace(k, "-" => "_"))
            env_key = "HTTP_" + k.replace("-", "_").upper()
            environ[env_key] = v

    return environ

def ancillary2sock(ancdata, family=socket.AF_INET, type=socket.SOCK_STREAM):
    """
    Abstracted Component: Extracts a raw file descriptor from POSIX ancillary data 
    (SCM_RIGHTS) and reconstructs it into a live, native Python socket object.
    """
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
            raw_fd = struct.unpack("i", cmsg_data)[0]
            return socket.fromfd(raw_fd, family, type)
    return None

def get_styled_date():
    # El formato %b devuelve el nombre del mes abreviado en inglés (Jan, Feb, Aug, etc.)
    # %z añade la desviación de la zona horaria actual (ej: -0300)
    return strftime("%d/%b/%Y:%H:%M:%S %z")

def load_application_target(target_str):
    """
    Dynamically loads the specified python target module and references 
    the targeted ASGI application variable.
    """
    if target_str == "none" or len(target_str) == 0:
        return None
    try:
        module_name, app_name = target_str.split(":")
        module = importlib.import_module(module_name)
        filename = getattr(module, "__file__", "")
        filepath = Path(filename).resolve()
        # os.chdir(filepath.parent)  # Change CWD to the module's directory for relative imports
        # sys.stdout.write(f"\n{CYAN}[PYTHON]{RESET} Current working directory changed to: {os.getcwd()}\n")
        return getattr(module, app_name)
    except Exception as e:
        sys.stdout.write(f"\n{CYAN}[PYTHON]{RESET} ❌ Python {'Worker'if '--worker' in sys.argv else 'Standalone Server'} failed to dynamically load app target '{target_str}': {e}\n")
        sys.stdout.flush()
        os._exit(1)

async def send_error_response(writer, 
    status_code:int,
    client_ip:str,
    request_line:str,
    server_version:str=VERSION, 
    msg:str="",
    ):
    try:
        status_phrase = HTTPStatus(status_code).phrase
    except:
        status_phrase = HTTPStatus(500).phrase
        status_code = 500

    if not msg:
        msg = status_phrase

    # 1. Craft the clean, professional monospace HTML layout
    html_error_payload = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{status_code} {status_phrase}</title>
        <style>
            body {{ font-family: 'monospace', sans-serif; margin: 3rem; background: #fafafa; color: #111; text-align: center; }}
            .error-container {{ max-width: 600px; margin: 0 auto; background: white; padding: 2.5rem; border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #eaeaea; }}
            h1 {{ font-size: 1.8rem; color: #cc3333; margin-top: 0; padding-bottom: 0.5rem; border-bottom: 1px solid #eaeaea; }}
            p {{ font-size: 1.1rem; color: #333; line-height: 1.6; }}
            .details {{ font-size: 0.9rem; color: #666; background: #f5f5f5; padding: 0.8rem; border-radius: 4px; text-align: left; word-break: break-all; margin-top: 1.5rem; }}
            .footer {{ margin-top: 2.5rem; border-top: 1px solid #eaeaea; padding-top: 0.8rem; font-size: 0.85rem; color: #666; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="error-container">
            <h1>{status_code} {status_phrase}</h1>
            <p>{msg}</p>
            <div class="details">
                <b>Client IP:</b> {client_ip}<br>
                <b>Request:</b> {request_line}<br>
                <b>Server Timestamp:</b> {get_styled_date()}
            </div>
        </div>
        <div class="footer">OxiServer/{server_version} (C++/Julia Powered ASGI Engine)</div>
    </body>
    </html>
    """
    
    html_bytes = html_error_payload.encode('utf-8')
    payload_length = len(html_bytes)

    try:
        #     # Emit strict HTTP/1.1 compliance packets
        writer.write(f"HTTP/1.1 {status_code} {status_phrase}\r\n".encode())
        writer.write("Content-Type: text/html; charset=utf-8\r\n".encode())
        writer.write(f"Content-Length: {payload_length}\r\n".encode())
        current_date = get_rfc_date()
        writer.write(f"Date: {current_date}\r\n".encode('utf-8'))
        writer.write(f"Server: OxiServer/{VERSION}\r\n".encode('utf-8'))

        writer.write("Connection: close\r\n".encode())
        writer.write("\r\n".encode()) # Mandatory delimiter boundary
        await writer.drain()    
        writer.write(html_bytes)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        try:
            method, path, protocol = request_line.split(' ') 
            scope = {"method": method, "path": path, "protocol": protocol}
            await log_access(scope, status_code, payload_length)
        except Exception as exc:
            excname = exc.__class__.__name__
            await log_msg(f"Error {excname}: {exc}\nLogging with empty scope")
            await log_access({}, status_code, payload_length)
    except:
        pass
        # Fail silently if the socket pipe was dropped by the client browser

async def get_response_headers(scope: dict, asgi_event: dict)-> list:
    http_version = scope.get("http_version", "1.1")
    evstatus = asgi_event.get("status")
    evstatus = int(str(evstatus)) if str(evstatus).isdigit() else 404
    status = HTTPStatus(evstatus)
    status_line = f"HTTP/{http_version} {status.value} {status.phrase}\r\n"

    headers = [to_bytes(status_line)]
    
    # Banderas para controlar duplicados o cabeceras conflictivas
    has_content_length = False
    has_connection = False
    is_redirect_or_empty = evstatus in [204, 301, 302, 303, 307, 308]

    for header_line in asgi_event.get("headers", []):
        if isinstance(header_line, (tuple, list)) and len(header_line) == 2:
            key, value = header_line
            key_lower = key.lower()
            
            # Si es una redirección, ignoramos cualquier Content-Length basura que mande la app
            if key_lower == b"content-length":
                has_content_length = True
                if is_redirect_or_empty:
                    value = b"0" # Forzamos a que sea cero
            
            if key_lower == b"connection":
                has_connection = True
                if is_redirect_or_empty:
                    value = b"close" # Forzamos cierre inmediato

            try:
                full_header_line = key + b": " + value + b"\r\n"
                headers.append(full_header_line)
            except Exception as exc:
                await log_msg(msg=f"Error while computing header line: {exc} - ({exc.__class__.__name__})")

    # Si la app no especificó Content-Length en la redirección, lo agregamos nosotros
    if not has_content_length and is_redirect_or_empty:
        headers.append(b"content-length: 0\r\n")
        
    # Si no se especificó Connection, forzamos close para asegurar que curl libere el cursor
    if not has_connection:
        headers.append(b"connection: close\r\n")

    # Corregimos el formato de fecha asegurando que el string de zona horaria no se mutile
    # current_date = strftime("%a, %d %b %Y %H:%M:%S %z")
    current_date = get_rfc_date()
    headers.append(f"Date: {current_date}\r\n".encode('utf-8'))
    headers.append(f"Server: OxiServer/{VERSION}\r\n".encode('utf-8'))
    headers.append(b"\r\n")
    return headers

async def get_content_length(scope: dict)-> int:
    for [key, value] in scope["headers"]:
        if key == b"content-length":
            val = to_bytes(value).decode('utf-8') if type(value) == bytes else value
            return int(val)
    return 0        

async def get_scope_headers(request):
    headers = [(k.lower().encode('latin-1'), v.encode('latin-1')) for k, v in request.get("headers", {}).items()]
    dict_headers = dict(headers)
    return headers, dict_headers

async def get_scope(request:dict, reader:asyncio.StreamReader, writer:asyncio.StreamWriter, app=None):
    global version
    scope = {}

    headers, dict_headers = await get_scope_headers(request)
    scope["headers"] = headers
    scope["_dict_headers"] = dict_headers # Internal use only
    scope["_reader"] = reader # Internal use only
    scope["_writer"] = writer # Internal use only
    scope["_oxi_version"] = request.get("version", version) # Internal use only

    remote_addr = writer.get_extra_info('peername')
    if "X-Forwarded-For".lower().encode() in dict_headers:
        remote_addr = (dict_headers["X-Forwarded-For".lower().encode()], remote_addr[1])
    if "X-Real-IP".lower().encode() in dict_headers:
        remote_addr = (dict_headers["X-Real-IP".lower().encode()], remote_addr[1])
    remote_ip, remote_port = remote_addr[:2]
    remote_port = int(remote_port) if remote_port else None
    remote_host = ["Unknown host"]
    client = (remote_addr[0], remote_port)

    transport = writer.transport
    sock = transport.get_extra_info('socket')

    local_addr = writer.get_extra_info('sockname')
    local_ip, local_port = local_addr[:2]
    local_port = int(local_port) if local_port else None
    server_name = f"OxiServer/{request.get('version', '0.0.1')}"


    method = request.get("method", "GET")
    path = request.get("path", "/")
    protocol = request.get("protocol", "HTTP/1.1")
    url = urlparse(path)
    __, http_version = protocol.split("/")

    oxi_version = request.get("version", version)
    more_scope = {
        "server_version": oxi_version,
        "server_software": f"Oxi (Asynchronous Server - Julia powered) {'v ' +  oxi_version}",
        "server_name": f"OxiServer/{oxi_version}",
        "gateway_interface": "CGI/1.1",
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": http_version,
        "method": method,
        "scheme": url.scheme or "http",
        "path": url.path,
        "query_string": request.get("query_string", "").encode('latin-1'),
        "x-real-ip": remote_ip,
        "remote-host": remote_host[0],
        "remote-port": str(remote_port) if remote_port else "null",
        "server_ip": local_ip,
        "local_port": str(local_port) if local_port else "null",
        "server_port": str(local_port) if local_port else "80",
        "client": client,
        "protocol": protocol,
        "_sock": sock,  # Internal use only
        "extensions:": {
            "type": "echo"
        },
        "request_body": request.get('body', b''),
    }
    scope.update(more_scope)

    if (
        method.upper() == "GET"
        and b"Upgrade" in dict_headers.get(b"connection", b"")
        and dict_headers.get(b"upgrade") == b"websocket"
    ):
        sec_websocket_protocol = dict_headers.get(b"sec-websocket-protocol", b"")
        subprotocols = [proto.strip() for proto in sec_websocket_protocol.split(b",")]
        scope.update({"type": "websocket", "subprotocols": subprotocols, "method": method, 
        "scheme": "ws"})
    else:
        scope.update({"type": "http", "method": method})
        if is_wsgi(app):
            environ = {
                "wsgi.version": (1, 0),
                "wsgi.url_scheme": scope.get("scheme", "http"),
                "wsgi.input": io.BytesIO(),
                # "wsgi.errors": io.BytesIO(),
                "wsgi.errors": sys.stderr,
                "wsgi.multithread": True,
                "wsgi.multiprocess": False,
                "wsgi.run_once": False,
                "GATEWAY_INTERFACE": "CGI/1.1",
                "SERVER_SOFTWARE": scope.get("server_software"),
                "REQUEST_METHOD": method.upper(),
                "SCRIPT_NAME": os.path.split(path)[1],
                "PATH_INFO": url.path,
                "QUERY_STRING": to_bytes(scope["query_string"]).decode("ascii"),
                # "QUERY_STRING": scope["query_string"],
                "SERVER_PROTOCOL": f'HTTP/{scope["http_version"]}',
                "SERVER_NAME": scope.get("server_name"),
                "SERVER_PORT": scope.get("server_port"),
                "REMOTE_ADDR": remote_ip,
            }

            for name, value in scope.get("headers", []):
                name = to_bytes(name).decode("latin-1")
                if name == "content-length":
                    corrected_name = "CONTENT_LENGTH"
                elif name == "content-type":
                    corrected_name = "CONTENT_TYPE"
                else:
                    corrected_name = f'HTTP_{name.upper().replace("-", "_")}'
                # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
                value = to_bytes(value).decode("latin-1")
                if corrected_name in environ:
                    value = environ[corrected_name] + "," + value
                environ[corrected_name] = value

            scope['_wsgi_environ'] = environ # For internal use only

    return scope

async def wsgi2asgi(scope: dict, receive: Callable, send: Callable, wsgi_callable: Callable) -> Callable:
    environ = scope.get("_wsgi_environ")
    if not environ:
        raise RuntimeError("WSGI environment is not set")
    
    if scope.get('method', 'GET').lower() not in ['get', 'head', 'options']:
        msg = await receive()
        body = msg.get('body', b'')
        environ['wsgi.input'] = io.BytesIO(body)

    status_str = "200 OK"
    headers_list = []
    # Usamos un bytearray común para acumular tanto lo que venga por el return iterable 
    # como lo que se envíe usando la función write() heredada de start_response
    body_buffer = bytearray()

    # Invocable exigido por PEP 3333 que start_response debe retornar
    def write_callback(data):
        if not isinstance(data, bytes):
            raise TypeError("WSGI write() argument must be a bytes object")
        body_buffer.extend(data)

    def start_response(status, headers, exc_info=None):
        nonlocal status_str, headers_list
        if exc_info and headers_list:
            # Si ya se enviaron o procesaron cabeceras y hay un error, 
            # el estándar exige relanzar la excepción si la app lo pide
            raise exc_info[1].with_traceback(exc_info[2])
            
        status_str = status
        headers_list = [(k.lower().encode('latin-1'), v.encode('latin-1')) for k, v in headers]
        
        # CUMPLIMIENTO PEP 3333: Retornamos el invocable de escritura síncrona
        return write_callback

    async def asgi_wrapper(scope: dict = scope, receive: Callable = receive, send: Callable = send):
        nonlocal status_str, headers_list, body_buffer
        
        # Ejecutamos la app de forma segura en el pool de hilos
        result = None
        if inspect.iscoroutinefunction(wsgi_callable):
            result = await wsgi_callable(environ, start_response)
        else:
            task = asyncio.create_task(asyncio.to_thread(wsgi_callable, environ, start_response))
            result = await task
        
        # 1. Consumimos el iterable retornado por la app (ej: Flask)
        if result is not None:
            lresult = []
            for chunk in result:
                if chunk:
                    lresult.append(chunk)
            # Combinamos los datos del iterable con lo que se haya acumulado en write_callback
            body_buffer.extend(b''.join(lresult))

        try:
            status_code = int(status_str.split(" ")[0])
        except Exception:
            status_code = 500

        # --- VALIDACIÓN Y PARCHE DE CABECERAS HTTP ---
        has_content_length = any(k == b'content-length' for k, _ in headers_list)
        has_connection = any(k == b'connection' for k, _ in headers_list)

        # Calculamos la longitud final real sumando ambos flujos de datos
        if not has_content_length:
            headers_list.append((b'content-length', str(len(body_buffer)).encode('ascii')))

        if not has_connection:
            headers_list.append((b'connection', b'close'))
        else:
            headers_list = [(k, b'close' if k == b'connection' else v) for k, v in headers_list]

        # 2. Despachamos los eventos de forma asíncrona y segura (Thread-safe)
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": headers_list
        })

        await send({
            "type": "http.response.body",
            "body": bytes(body_buffer),
            "more_body": False
        })

        close_method = getattr(result, "close", None)
        if close_method is not None and callable(close_method):
            close_method()

       # LLAMADA AL LOG COMPATIBLE CON NGINX
        await log_access(scope, status_code, len(body_buffer))

    return asgi_wrapper

async def http_handler(scope, reader: asyncio.StreamReader, writer, app):
    response_headers = []
    headers_sent = False
    
    # Usamos un diccionario de contexto atómico. 
    # Python pasa los diccionarios por referencia, garantizando que cualquier 
    # cambio dentro de send() sea visible instantáneamente en el bloque except.
    tx_state = {
        "status_code": 200,
        "bytes_sent": 0,
        "logged": False
    }

    async def receive()-> dict:
        if not scope:
            return {}

        if len(scope.get('request_body', b'')):
            body = base64.b64decode(scope.get('request_body'))
            # print(f"Body preloaded of length '{len(body)}'")
            return {
                "type": "http.request",
                "body": to_bytes(body),
                "length": len(body),
                "more_body": False,
            }

        content_length = await get_content_length(scope)
        body = b''
        if scope.get('method', 'GET').lower() in ['post', 'put', 'patch']:
            retries = 0
            max_retries = 5
            while True:
                try:
                    morebody = await asyncio.wait_for(reader.read(1024), timeout=1)
                    body += morebody
                    await asyncio.sleep(0)
                    if len(body) >= content_length or len(morebody) == 0:
                        break
                except asyncio.TimeoutError:
                    await asyncio.sleep(0)
                    await reader.read(0)
                    await asyncio.sleep(0.01)
                    retries += 1
                    msg = f"{' ' * 15} - - [{get_styled_date()}] Timed out waiting for request body. Retry {retries}"
                    await log_msg(msg)
                    if retries >= max_retries:
                        await send_error_response(writer, 500, scope.get('client', ['localhost', 0])[0],
                                                         f"HTTP/1.1 {scope.get('method', 'get').upper()} {scope.get('path', '/')}",
                                                        scope.get('oxi_version', '0.0.1'),msg=msg)
                        break

        scope["request_body"] = body
        return {
            "type": "http.request",
            "body": body,
            "length": len(body),
            "more_body": False,
        }

    async def send(event: dict)-> None:
        nonlocal response_headers, headers_sent
        if not scope or scope == {}:
            return
            
        if event["type"] == "http.response.start":
            if headers_sent:
                return
            # Registramos el código numérico real en el diccionario de referencia de forma inmediata
            tx_state["status_code"] = int(event.get("status", 200))
            response_headers = await get_response_headers(scope, event)            
            
            # Intentamos enviar cabeceras rápido
            try:
                writer.writelines(response_headers)
                await writer.drain()
                response_headers = []
                headers_sent = True
            except ConnectionResetError:
                writer.close()
                return
            except BrokenPipeError:
                writer.close()
                return
            except Exception as exc:
                writer.close()
                await log_msg(f"Exception during sending response headers: {exc} - ({exc.__class__.__name__})")
            return
            
        elif event["type"] == "http.response.body":
            if not headers_sent and len(response_headers) != 0:
                try:
                    writer.writelines(response_headers)
                    await writer.drain()
                    response_headers = []
                    headers_sent = True
                except ConnectionResetError:
                    writer.close()
                    return
                except BrokenPipeError:
                    writer.close()
                    return
                except Exception as exc:
                    writer.close()
                    await log_msg(f"Exception during sending response headers: {exc} - ({exc.__class__.__name__})")
                    return
        else:
            await log_msg(f"Unknown event type: '{event['type']}'")
            return
        
        body = event.get("body", b"")
        if body:
            tx_state["bytes_sent"] += len(body)
            try:
                writer.write(body) 
            except ConnectionResetError:
                try:
                    writer.close()
                except:
                    pass
                if not is_wsgi(app) and not tx_state["logged"]:
                    await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
                    tx_state["logged"] = True
                return
            except BrokenPipeError:
                try:
                    writer.close()
                except:
                    pass
                if not is_wsgi(app) and not tx_state["logged"]:
                    await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
                    tx_state["logged"] = True
                return
            except Exception as exc:
                try:
                    writer.close()
                except:
                    pass
                # Si el socket se rompe aquí, registramos el log con los datos reales guardados
                # await log_msg(f"Exception occurred while sending body chunk: {exc} - ({exc.__class__.__name__})")
                if not is_wsgi(app) and not tx_state["logged"]:
                    await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
                    tx_state["logged"] = True
                raise 

        if event.get("more_body", False) is False:
            try:
                if not headers_sent and len(response_headers) != 0:
                    writer.writelines(response_headers)
                    await writer.drain()
                    headers_sent = True
                
                await writer.drain()
                
                # Emitimos el log en el flujo feliz antes de cerrar
                if not is_wsgi(app) and not tx_state["logged"]:
                    try:
                        await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
                    except:
                        pass
                    tx_state["logged"] = True
                
                writer.close()
                await writer.wait_closed()
            except ConnectionResetError:
                writer.close()
                return
            except BrokenPipeError:
                writer.close()
                return
            except Exception as exc:
                writer.close()
                await log_msg(f"Exception '{exc.__class__.__name__}' occurred in file {__file__} at line {'inspect.currentframe().f_lineno'} while sending final body chunk: {exc}")
                if not is_wsgi(app) and not tx_state["logged"]:
                    await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
                    tx_state["logged"] = True
    try:
        if is_wsgi(app):
            wapp = await wsgi2asgi(scope, receive, send, app)
            await wapp(scope, receive, send)
        else:
            await app(scope, receive, send)
    except ConnectionResetError:
        writer.close()
        return
    except BrokenPipeError:
        writer.close()
        return
    except Exception as exc:
        writer.close()
        await log_msg(f"Exception occurred in file {__file__}, line No {'inspect.currentframe().f_lineno'} while awaiting app: {exc} - ({exc.__class__.__name__})")
        # Si el flujo se cae debido a que el cliente cerró el socket en plena ráfaga, 
        # el diccionario tx_state tendrá el código real mutado por send() de forma garantizada.
        # if not is_wsgi(app) and not tx_state["logged"]:
        if not tx_state["logged"]:
            await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
            tx_state["logged"] = True
        
        # Solo imprimimos un error 500 real si no fue un descarte de tubería del socket
        exc_str = str(exc).lower()
        if "connection" not in exc_str and "pipe" not in exc_str:
            try:
                await send_error_response(writer, 500, scope.get("client", ["localhost", 0])[0],
                    f'{scope.get("method", "GET?")} {scope.get("path", "/?")}',
                    # server_version=scope.get("_oxi_version", "0.0.1"),
                    server_version=VERSION,
                    msg=f"{exc} - ({exc.__class__.__name__})")
            except Exception:
                pass

async def websocket_handler(scope, reader, writer, app):
    def make_upgrade_response():
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        dict_headers = dict(scope["headers"])
        # Buscamos la cabecera 'Sec-WebSocket-Key' ignorando mayúsculas/minúsculas
        key = ""
        for k, v in dict_headers.items():
            if to_bytes(k).lower() == b"sec-websocket-key":
                key = to_bytes(v).decode().strip()
                break
                
        if not key:
            raise KeyError("Sec-WebSocket-Key header is missing from handshake request")
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
        masking_key = []

        # Read frame header
        try:
            header = await reader.read(2)
            if len(header) < 2:
                raise ConnectionResetError("Client disconnected mid-frame")    
        except Exception as exc:
            await log_msg(f"Exception occurred while trying to read frame: {repr(exc)}")
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
            if len(header) < 8:
                raise ConnectionResetError("Client disconnected mid-frame")    
            u = struct.unpack("<Q", l)
            payload_len = u[0]

        if mask:
            masking_key = await reader.read(4)

        # 🚀 ENFORCE PAYLOAD LIMIT BEFORE READING
        if payload_len > MAX_WS_PAYLOAD:
            # Per RFC 6455, close code 1009 = "Message Too Big"
            raise ConnectionError(f"WebSocket frame too large: {payload_len} bytes")

        payload = await reader.read(payload_len)

        if mask:
            payload = bytes(payload[i] ^ masking_key[i % 4] for i in range(len(payload)))

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
            event = {"type": "websocket.receive", "text": to_bytes(payload).decode()}
        elif opcode == 2:
            event = {"type": "websocket.receive", "bytes": to_bytes(payload)}
        elif opcode == 8:
            close_code = 1005  # Default
            if len(payload):
                u = struct.unpack(">H", payload)
                close_code = u[0]
            return {"type": "websocket.disconnect", "code": close_code}
        elif opcode == 9:
            event = {"type": "websocket.ping", "bytes": payload}
#                await log_msg("\nPING frame received.")
#                await log_msg(f"fin: {fin} - opcode: {opcode} - payload: {payload}")
        elif opcode == 10:
            event = {"type": "websocket.pong", "bytes": payload}
#                await log_msg("\nPONG frame received.")
#                await log_msg(f"fin: {fin} - opcode: {opcode} - payload: {payload}")
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
                await log_msg(f"Exception occurred in send websocket coroutine accepting connection: {exc} - ({exc.__class__.__name__})")
                raise
        elif ev_type == "websocket.ping" or ev_type == "websocket.pong" or ev_type == "websocket.send":
            # App's sending data
            frame = make_websocket_frame(event)
            try:
                writer.write(frame)
                await writer.drain()
            except Exception as exc:
                await log_msg(f"Exception occurred in send websocket coroutine while sending frame: {exc} - ({exc.__class__.__name__})")
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
                await log_msg(f"Exception occurred in send websocket coroutine while closing connection: {exc} - ({exc.__class__.__name__})")
                raise

    # Invoke the app!
    try:
        await app(scope, receive, send)
    except ConnectionError as exc:
        # A protocol-level error in the frame (bad length, malformed bytes, etc.)
        # Send a proper WebSocket close frame to the client, then stop.
        await log_msg(f"[WebSocket] Protocol error: {exc}")
        try:
            # 1009 = Message Too Big, 1002 = Protocol Error
            code = 1009 if "too large" in str(exc).lower() else 1002
            writer.write(bytes([0x88, 2]) + code.to_bytes(2, "big"))
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    except Exception as exc:
        etype, _, tb = sys.exc_info()
        await log_msg(f"Exception '{etype}' occurred in websocket handler: {exc}")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
    
async def process_message(client_sock, request, python_app, reader=None, writer=None):
    scope = {}
    try:
        # If reader/writer aren't provided (Slave Mode), we initialize them from the adopted socket.
        # If they are provided (Standalone Mode), we reuse the native server transports directly.
        if reader is None or writer is None:
            reader, writer = await asyncio.open_connection(sock=client_sock)
            
        scope = await get_scope(request, reader, writer, python_app)
        
        if scope.get("type") == 'http':
            await http_handler(scope, reader, writer, python_app)
        elif scope.get("type") == 'websocket':
            await websocket_handler(scope, reader, writer, python_app)
        else:
            await send_error_response(writer, 400, 
                                      scope.get("client", ["localhost", 0]), 
                                      f'{scope.get("method", "GET?")} {scope.get("path", "/?")}',
                                    #   server_version=scope.get("_oxi_version", "0.0.1"),
                                      server_version=VERSION,
                                      msg=f"Message type \'{scope.get('type')}\' not supported.")
    except Exception as exc:
        exc_str = str(exc).lower()
        if "connection" not in exc_str and "pipe" not in exc_str:
            await log_msg(f"ERROR inside process_message cluster: {exc} - ({exc.__class__.__name__})")
            try:
                await send_error_response(writer, 500, 
                                            scope.get("client", ["localhost", 0]), 
                                            f'{scope.get("method", "GET?")} {scope.get("path", "/?")}',
                                            server_version=VERSION,
                                            msg=f"ERROR:\n{exc} - ({exc.__class__.__name__})")
            except Exception:
                pass

def julia_bridge_parse_request(socket_fd: int) -> str:
    """
    Permite a Julia delegar el parseo inicial de HTTP a Python pasándole el FD del socket.
    Devuelve un string JSON con el request formateado.
    """
    # Reconstruimos temporalmente el socket en Python para leer las cabeceras
    sock = socket.fromfd(socket_fd, socket.AF_INET, socket.SOCK_STREAM)
    # Creamos un archivo de lectura de buffers de texto ordinario
    sock_file = sock.makefile('rb')
    
    try:
        request_dict = parse_http_stream(lambda: sock_file.readline())
        return json.dumps(request_dict) if request_dict else "null"
    finally:
        # Desacoplamos el archivo sin cerrar el socket físico real
        sock_file.close()
        sock.detach()

async def run_lifespan(app, loop):
    global _lifespan_ready
    receive_queue = asyncio.Queue()
    shutdown_event = asyncio.Event()
    startup_complete_event = asyncio.Event()
    startup_error = None
    task_done = False  # 🚀 Track if the app returned

    # 🚀 WSGI apps don't support lifespan. Skip the protocol.
    if is_wsgi(app):
        print(f"\n\033[33m[Lifespan]\033[0m WSGI app detected. Skipping ASGI Lifespan protocol.")
        _lifespan_ready = True
        # Return a dummy task and queues so C++ shutdown logic doesn't crash
        shutdown_event.set()
        dummy_task = asyncio.create_task(asyncio.sleep(0)) 
        return receive_queue, shutdown_event, dummy_task

    async def receive():
        return await receive_queue.get()

    async def send(message):
        nonlocal startup_error, task_done
        if message['type'] == 'lifespan.startup.complete':
            startup_complete_event.set()
        elif message['type'] == 'lifespan.startup.failed':
            startup_error = message.get('message', 'Unknown error')
            startup_complete_event.set()
        elif message['type'] == 'lifespan.shutdown.complete':
            shutdown_event.set()
        elif message['type'] == 'lifespan.shutdown.failed':
            shutdown_event.set()
        elif message['type'] == 'lifespan.shutdown':
            task_done = True

    scope = {
        "type": "lifespan",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "state": {"server": f"OxiServer/{VERSION}"}
    }

    async def app_wrapper():
        nonlocal task_done
        try:
            await app(scope, receive, send)
        except Exception as e:
            print(f"\n\033[33m[Lifespan]\033[0m App does not support lifespan: {e}")
        finally:
            task_done = True # 🚀 App finished (either via exception or return)

    app_task = asyncio.create_task(app_wrapper())

    await receive_queue.put({"type": "lifespan.startup"})

    startup_wait_task = asyncio.create_task(startup_complete_event.wait())

    # 🚀 Wait for startup to complete OR the app to return
    done, pending = await asyncio.wait(
        [startup_wait_task, app_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    if startup_error is not None:
        app_task.cancel()
        raise LifespanStartupError(startup_error)
    
    if not startup_complete_event.is_set():
        # The app returned before sending startup.complete
        print(f"{CYAN}[Python Worker]{RESET} App returned without lifespan handshake. Skipping protocol.")
        startup_wait_task.cancel()
        _lifespan_ready = True
        shutdown_event.set() 
        dummy_task = asyncio.create_task(asyncio.sleep(0)) 
        return receive_queue, shutdown_event, dummy_task

    print(f"{CYAN}[Python Worker]{RESET} Lifespan startup complete.")
    _lifespan_ready = True
    return receive_queue, shutdown_event, app_task

def run_standalone_server(host: str, port: int, python_app, loop: asyncio.AbstractEventLoop):

    # =====================================================================
    # 🟢 MODE 1: STANDALONE 
    # =====================================================================
    async def standalone_client_callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_sock = writer.get_extra_info('socket')
        if client_sock is None:
            writer.close()
            return

        request_data = None
        try:    
            request_data = await parse_standalone_request(reader)
        except KeyboardInterrupt:
            return
        if request_data:
            loop.create_task(process_message(client_sock, request_data, python_app, reader, writer))
        else:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start_standalone_server():
        if uvloop_available:
            print(f"{CYAN}[Python Worker]{RESET} Asyncio using Uvloop.")
        else:
            print(f"{CYAN}[Python Worker]{RESET} Uvloop not available.")
        print(f"{CYAN}[Python Worker]{RESET} Starting Lifespan protocol...")

        
        try:
            l_receive_q, l_shutdown_event, l_task = await run_lifespan(python_app, loop)
        except LifespanStartupError as e:
            print(f"\n\033[31m[Server]\033[0m Aborting startup: {e}")
            return

        server = await asyncio.start_server(standalone_client_callback, host, port, reuse_address=True, reuse_port=True)
        sys.stdout.write(f"\nPYTHON: 🚀 Oxi-Standalone ASGI/WSGI Server active at http://{host}:{port} (PID: {os.getpid()})\n")
        sys.stdout.flush()
        
        # 🚀 Create an event to signal shutdown gracefully
        stop_event = asyncio.Event()

        def signal_handler():
            print(f"\nPYTHON: 🚀 Oxi-Standalone Server leaving the stage... (PID: {os.getpid()}).")
            stop_event.set()

        # Register the signal handlers for the event loop
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

        try:
            # Serve until the stop_event is set
            async with server:
                await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            # 🚀 The shutdown logic runs INSIDE the coroutine, BEFORE the loop closes
            print(f"\n{CYAN}[Python Worker]{RESET} Sending lifespan.shutdown...")
            try:
                await l_receive_q.put({"type": "lifespan.shutdown"})
                await asyncio.wait_for(l_shutdown_event.wait(), timeout=5.0)
                await l_task
                print(f"{CYAN}[Python Worker]{RESET} Lifespan shutdown complete.")
            except asyncio.TimeoutError:
                print(f"{CYAN}[Python Worker]{RESET} App did not respond to lifetime shutdown in time. Forcing exit.")
                os._exit(1)
            except Exception as e:
                print(f"{CYAN}[Python Worker]{RESET} Lifespan shutdown error: {e}")
                os._exit(1)

    try:
        loop.run_until_complete(start_standalone_server())
    except KeyboardInterrupt:
        # Fallback in case the signal handler didn't catch it
        sys.stdout.write(f"\nPYTHON: 🚀 Oxi-Standalone Server leaving the stage... (PID: {os.getpid()}).\n")
        sys.stdout.flush()
    finally:
        loop.close()

def run_worker_server(python_app, loop: asyncio.AbstractEventLoop):
        # =====================================================================
        # 🟡 MODO 2: ESCLAVO (Tándem Híbrido coordinado por Julia)
        # =====================================================================
        UNIX_SOCKET_PATH = "/tmp/julia_python.sock"
        if os.path.exists(UNIX_SOCKET_PATH):
            os.remove(UNIX_SOCKET_PATH)
            
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(UNIX_SOCKET_PATH)
        server.listen(128)
        server.setblocking(False)
        
        async def read_and_dispatch(julia_conn):
            chsize = 8192 * 4
            try:
                ancsize = socket.CMSG_SPACE(struct.calcsize("i"))
                json_bytes, ancdata, flags, addr = julia_conn.recvmsg(chsize, ancsize)
                
                # --- CIRCUITO TOLERANTE A FRAGMENTACIÓN UNIX ---
                # Si llegaron los descriptores pero el JSON se retrasó en el bus local,
                # cedemos un micro-tick al loop y re-intentamos leer el remanente
                retry = 0
                while not json_bytes and retry < 3:
                    retry += 1
                    await asyncio.sleep(0.005)
                    json_bytes, _, _, _ = julia_conn.recvmsg(chsize)

                while True:
                    await asyncio.sleep(0.005)
                    more_bytes , _, _, _ = julia_conn.recvmsg(chsize)
                    if more_bytes:
                        json_bytes += more_bytes
                    else:
                        break

                julia_conn.close()

                if not json_bytes:
                    return # Si tras los reintentos está vacío, salimos de forma segura
                    
                request_data = json.loads(to_bytes(json_bytes).decode('utf-8'))
                client_sock = ancillary2sock(ancdata)
                
                if client_sock is not None:
                    loop.create_task(process_message(client_sock, request_data, python_app))
                else:
                    sys.stdout.write("\nPYTHON: ⚠️ Warning: Socket descriptor empty from Julia.\n")
                    sys.stdout.flush()
            except Exception as e:
                sys.stdout.write(f"\nPYTHON: ❌ Error in connection dispatch pipeline: {e}\n")
                sys.stdout.flush()
            finally:
                try: 
                    julia_conn.close() 
                except Exception: 
                    pass

        def handle_julia_connection():
            try:
                julia_conn, _ = server.accept()
                julia_conn.setblocking(True)
            except BlockingIOError:
                return
            except Exception as e:
                sys.stdout.write(f"\nPYTHON: ❌ Error accepting Julia connection: {e}\n")
                sys.stdout.flush()
                return
            loop.create_task(read_and_dispatch(julia_conn))

        loop.add_reader(server.fileno(), handle_julia_connection)
        
        sys.stdout.write(f"\nPYTHON: 🚀 Oxi Worker fully operational in single asynchronous thread (PID: {os.getpid()}).\n")
        sys.stdout.flush()

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            sys.stdout.write(f"\nPYTHON: 🚀 Oxi Worker leaving the stage... (PID: {os.getpid()}).\n")
            sys.stdout.flush()
        finally:
            loop.close()

def run(app, host:str="0.0.0.0", port:int=8086):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        run_standalone_server(host, port, app, loop) 
    except KeyboardInterrupt:
        sys.stdout.write(f"\nPYTHON: 🚀 Oxi-Standalone Server leaving the stage... (PID: {os.getpid()}).\n")
        sys.stdout.flush()
    finally:
        loop.close()

def embedded_send_html_error(socket_fd: int, status_code: int, msg: str, path: str, client_ip: str, method: str):
    """
    C++ Direct Error Entrypoint.
    Receives the true client IP tracked by C++ to avoid proxy masking.
    """
    global _embedded_global_loop
    if _embedded_global_loop is None:
        return

    client_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, fileno=socket_fd)
    client_sock.setblocking(False)

    async def async_error_worker():
        try:
            reader, writer = await asyncio.open_connection(sock=client_sock)
            # request_line = f"GET {path} HTTP/1.1"
            request_line = f"{method} {path} HTTP/1.1"
            
            # 🚀 USAMOS LA IP PROVISTA POR C++ DIRECTAMENTE
            await send_error_response(writer, status_code, client_ip, request_line, VERSION, msg=msg)
        except Exception as e:
            sys.stdout.write(f"\nPYTHON ERROR WORKER ❌ Error rendering HTML response: {e}\n")
            sys.stdout.flush()
        finally:
            try:
                client_sock.close()
                # os.close(socket_fd)
            except OSError:
                pass

    asyncio.run_coroutine_threadsafe(async_error_worker(), _embedded_global_loop)

def embedded_send_directory_listing(socket_fd: int, path: str, client_ip: str):
    """
    C++ Direct Directory Listing Entrypoint.
    Bypasses the full ASGI pipeline to immediately render a clean Nginx-style
    directory index using the existing logic in static.py.
    """
    global _embedded_global_loop
    if _embedded_global_loop is None:
        return

    # Importación tardía para evitar acoplamientos circulares
    import static 

    client_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, fileno=socket_fd)
    client_sock.setblocking(False)

    async def async_dir_worker():
        tx_state = {
        "status_code": 200,
        "bytes_sent": 0,
        "logged": False
        }


        try:
            reader, writer = await asyncio.open_connection(sock=client_sock)
            
            # Reconstruimos un scope ASGI mínimo y compatible exigido por static.handle_send_dir
            scope = {
                "type": "http",
                "path": path,
                "method": "GET",
                "client": [client_ip.encode('latin-1'), 0],
                "protocol": "HTTP/1.1"
            }

            # Creamos un emulador simplificado del canal 'send' ASGI usando directamente el writer
            async def mock_send(event: dict):
                if event["type"] == "http.response.start":
                    tx_state["status_code"] = int(event.get("status", 200))
                    status_line = f"HTTP/1.1 {event['status']} OK\r\n"
                    writer.write(status_line.encode())
                    for k, v in event.get("headers", []):
                        writer.write(k + b": " + v + b"\r\n")
                    writer.write(b"\r\n")
                    await writer.drain()
                elif event["type"] == "http.response.body":
                    body = event.get("body", b"")
                    if body:
                        tx_state["bytes_sent"] += len(body)
                        writer.write(body)
                    if not event.get("more_body", False):
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                        if not tx_state["logged"]:
                            await log_access(scope, tx_state["status_code"], tx_state["bytes_sent"])
                            tx_state["logged"] = True


            # Delegamos la renderización visual completa al motor existente de la suite
            await static.handle_send_dir(scope, mock_send)
            
        except Exception as e:
            sys.stdout.write(f"\nPYTHON DIR WORKER ❌ Error rendering directory index: {e}\n")
            sys.stdout.flush()
        finally:
            try:
                client_sock.close()
                # os.close(socket_fd)
            except OSError:
                pass

    # Agendamos de forma segura en la hebra del loop permanente
    asyncio.run_coroutine_threadsafe(async_dir_worker(), _embedded_global_loop)

def embedded_run_cgi(socket_fd: int, method: str, path: str, query_string: str, protocol: str, client_ip: str, raw_headers_json: str, body_bytes: bytes):
    """
    C++ Direct CGI Execution Entrypoint.
    Bypasses string tokenization by accepting a native PyDict object directly from C++.
    """
    global _embedded_global_loop
    if _embedded_global_loop is None:
        return

    import static
    import json # Requerido

    client_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, fileno=socket_fd)
    client_sock.setblocking(False)

    async def async_cgi_worker():
        try:
            reader, writer = await asyncio.open_connection(sock=client_sock)
            
            # 🚀 RESTAURADO: Des-serializar la cadena JSON perfecta generada por C++
            headers_dict = json.loads(raw_headers_json)
            headers_list = [(k.encode('latin-1'), v.encode('latin-1')) for k, v in headers_dict.items()]
            
            # Creamos un scope CGI/1.1 compatible con la especificación de tu handle_cgi
            scope = {
                "type": "http",
                "http_version": protocol.split("/")[-1] if "/" in protocol else "1.1",
                "protocol": protocol,
                "method": method.upper(),
                "path": path,
                "query_string": query_string.encode('latin-1'),
                "headers": headers_list,
                "server_name": "OxiServer/C++ Hybrid Core",
                "local_port": str(client_sock.getsockname()[1]),
                "remote-host": "Unknown",
                "remote-port": str(client_sock.getpeername()[1]) if client_sock.getpeername() else "0",
                "x-real-ip": client_ip,
                "client": [client_ip.encode('latin-1'), 0]
            }

            body_consumed = False

            # Simulamos el canal 'receive' de ASGI inyectando los bytes ya leídos por C++
            async def mock_receive():
                nonlocal body_consumed
                if not body_consumed:
                    body_consumed = True
                    return {
                        "type": "http.request",
                        "body": body_bytes,
                        "length": len(body_bytes),
                        "more_body": False
                    }
                else:
                    return {
                    "type": "http.request",
                    "body": b"",
                    "length": 0,
                    "more_body": False
                }

            # Emulamos el canal 'send' de ASGI para volcar las respuestas directo al writer
            async def mock_send(event: dict):
                if event["type"] == "http.response.start":
                    status_line = f"HTTP/1.1 {event['status']} OK\r\n"
                    writer.write(status_line.encode())
                    for k, v in event.get("headers", []):
                        writer.write(k + b": " + v + b"\r\n")
                    writer.write(b"\r\n")
                    await writer.drain()
                elif event["type"] == "http.response.body":
                    body = event.get("body", b"")
                    if body:
                        writer.write(body)
                    if not event.get("more_body", False):
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()

            # Disparamos el motor de subprocesos nativo de tu suite
            await static.handle_cgi(scope, mock_receive, mock_send)
            
        except Exception as e:
            sys.stdout.write(f"\nPYTHON CGI WORKER ❌ Error executing subprocess: {e}\n")
            sys.stdout.flush()
        finally:
            try:
                client_sock.close()
                # os.close(socket_fd)
            except OSError:
                pass

    asyncio.run_coroutine_threadsafe(async_cgi_worker(), _embedded_global_loop)

def run_from_socket(socket_fd: int, python_app):
    """
    C++ Embedded Bridge Entrypoint.
    Reconstructs the native network descriptors and hands off the I/O processing
    to the background asyncio global event loop cleanly without IPC.
    """
    global _embedded_global_loop
    
    if _embedded_global_loop is None:
        sys.stdout.write("\nPYTHON EMBEDDED ❌ Error: Global event loop reference is missing!\n")
        sys.stdout.flush()
        return

    # Wrap the raw C++ file descriptor
    client_sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, fileno=socket_fd)
    client_sock.setblocking(False)

    async def async_bridge_worker():
        # Track if asyncio took full management custody of the descriptor
        asyncio_adopted = False
        try:
            # Atomic native adaptation to standard asyncio Stream transports
            reader, writer = await asyncio.open_connection(sock=client_sock)
            asyncio_adopted = True # Asyncio now owns client_sock and socket_fd completely
            
            # Use Oxi-Server's fast header parser directly on the active stream
            request_data = await parse_standalone_request(reader)
            
            if request_data:
                # Dispatch the full state execution to the Oxi core handler
                await process_message(client_sock, request_data, python_app, reader, writer)
            else:
                writer.close()
                await writer.wait_closed()
        except Exception as e:
            sys.stdout.write(f"\nPYTHON EMBEDDED ❌ Error processing socket bridge: {e}\n")
            sys.stdout.flush()
            if not asyncio_adopted:
                try:
                    client_sock.close() # This naturally closes socket_fd inside the kernel safely
                except OSError:
                    pass
    # Schedule the task directly into the shared loop thread-safely
    asyncio.run_coroutine_threadsafe(async_bridge_worker(), _embedded_global_loop)

def main():
    grandma_phone = "555-4823"

    if len(sys.argv) < 2:
        app_target_str = "static:static_app"        
    else:
        app_target_str = sys.argv[1]
    python_app = load_application_target(app_target_str)

    # --- DETECCIÓN E INICIALIZACIÓN DE ARGUMENTOS ---
    # is_standalone = "--standalone" in sys.argv
    is_worker = "--worker" in sys.argv

    host = "0.0.0.0"
    port = 8086  # Puerto por defecto para modo standalone independiente
    loop = None

    for arg in sys.argv:
        if arg.startswith("--host="):
            host = arg.split("=")[1]
        elif arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
            except ValueError:
                pass
    # if Path(options_virtual_env_path).is_dir() and uvloop_available:
    if uvloop_available:
        try:
            import uvloop  # pyright: ignore[reportMissingImports]
            loop = uvloop.new_event_loop()
            uvloop.install()
        except:
            loop = asyncio.new_event_loop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # if is_standalone:
    if not is_worker:
        subprocess.run("clear")
        run_standalone_server(host, port, python_app, loop)
    else:
        run_worker_server(python_app, loop)

if __name__ == "__main__":
    main()

