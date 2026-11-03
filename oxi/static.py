#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio, sys, os, json, shutil, mimetypes, io
from concurrent.futures import ThreadPoolExecutor
import http as http_module
from pathlib import Path

filepath = Path(__file__)
parentpath = filepath.parent
grandparentpath = parentpath.parent
pyversion = ""
pyexecutor = ""

sep = os.path.sep
options_virtual_env_path = f"{parentpath}{sep}.options-virtual-env"
examples_virtual_env_path = ""
if Path(options_virtual_env_path).is_dir():
    pyversion = os.listdir(f"{options_virtual_env_path}{sep}lib{sep}")[0]
    pyexecutor = f"{options_virtual_env_path}{sep}bin{sep}python3"
    options_virtual_env_path = f"{options_virtual_env_path}{sep}lib{sep}{pyversion}{sep}site-packages"
else:
    examples_virtual_env_path = f"{parentpath}{sep}.examples-virtual-env"
    if Path(examples_virtual_env_path).is_dir():
        pyversion = os.listdir(f"{examples_virtual_env_path}{sep}lib{sep}")[0]
        pyexecutor = f"{examples_virtual_env_path}{sep}bin{sep}python3"
        examples_virtual_env_path = f"{examples_virtual_env_path}{sep}lib{sep}{pyversion}{sep}site-packages"

if Path(options_virtual_env_path).is_dir() and  not options_virtual_env_path in sys.path:
    sys.path.insert(0, examples_virtual_env_path)
elif Path(examples_virtual_env_path).is_dir() and not examples_virtual_env_path in sys.path and not Path(options_virtual_env_path).is_dir():
    sys.path.insert(0, options_virtual_env_path)
if not str(parentpath) in sys.path:
    sys.path.insert(0, str(parentpath))
if not str(grandparentpath )in sys.path:
    sys.path.insert(0, str(grandparentpath))

try:
    from server import get_styled_date, log_msg
    from utils import to_bytes, bytes_to_human_readable
except:
    try:
        from .server import get_styled_date, log_msg
        from .utils import to_bytes, bytes_to_human_readable
    except:
        from server import get_styled_date, log_msg
        from utils import to_bytes, bytes_to_human_readable

if not (os.getcwd() in sys.path):
    sys.path.insert(0, os.getcwd())

def base_dir():
    """
    Returns the absolute path of the directory containing the current Julia script.
    """
    return os.path.dirname(os.path.abspath(__file__))

basedir = base_dir()

if not (basedir in sys.path):
    sys.path.insert(0, basedir)


def load_config():
    """
    Reads the config.json file and transforms it into a global dictionary.
    If the file does not exist, it provides a secure default environment.
    """
    ruta_config = os.path.join(os.getcwd(), "config.json")
    
    # Valores por defecto idénticos a tu especificación JSON
    from __about__ import __version__ as pyversion
    from __about__ import __config__ as default_config
    default_config["version"] = pyversion  # Aseguramos que la versión sea un string

    if os.path.isfile(ruta_config):
        try:
            # JSON.parsefile abre el archivo y genera un Dict{String, Any} nativo
            with open(ruta_config, 'r', encoding='utf-8') as fd:
                config_data = json.load(fd)
                config_data["version"] = pyversion  # Aseguramos que la versión sea un string
                return config_data
        except Exception as e:
            print(f"⚠️ Error leyendo config.json, usando valores por defecto: {e}", file=sys.stderr, flush=True)
            return default_config
    else:
        return default_config

CONFIG = load_config()

staticdir = CONFIG.get("static_dir", "static")
if not os.path.isdir(staticdir):
    if __name__ == '__main__':
        print(f"⚠️ Alert: static directory '{staticdir}' does not exist. Using base directory instead.", file=sys.stderr, flush=True)
    staticdir = ""
    CONFIG["static_dir"] = staticdir

def save_config(config:dict= CONFIG):
    ruta_config = os.path.join(os.getcwd(), "config.json")
    with open(ruta_config, "w", encoding='utf-8') as fd:
        json.dump(config, fd)

PHP_BINARY_PATH = None  # Busca el ejecutable de PHP en el PATH del sistema

def probe_php_runtime():
    global PHP_BINARY_PATH
    candidates = ["php-cgi", "php"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            PHP_BINARY_PATH = path
            break

probe_php_runtime()

MIME_TYPES = {}

def init_mime_types():
    """
    Inicializa el mapa de tipos MIME trayendo el diccionario completo de la librería estándar de Python.
    """
    global MIME_TYPES
    try:
        mimetypes.init()
        
        MIME_TYPES = mimetypes.types_map.copy()  # Copiamos el diccionario de tipos MIME de Python       
        # Agregamos manualmente un par de defaults comunes por si faltan en algunas distros
        if ".js" not in MIME_TYPES:
            MIME_TYPES[".js"] = "application/javascript; charset=utf-8"
        if ".css" not in MIME_TYPES:
            MIME_TYPES[".css"] = "text/css; charset=utf-8"
        if ".html" not in MIME_TYPES:
            MIME_TYPES[".html"] = "text/html; charset=utf-8"
        
    except Exception as e:
        print(f"⚠️ Alerta: No se pudo cargar mimetypes de Python, usando defaults mínimos: {e}", file=sys.stderr, flush=True)
        MIME_TYPES[".html"] = "text/html; charset=utf-8"
        MIME_TYPES[".css"]  = "text/css; charset=utf-8"
        MIME_TYPES[".js"]   = "application/javascript; charset=utf-8"

init_mime_types()

def get_mime_type(ruta_archivo: str) -> str:
    """
    Returns the MIME type for a given file path based on its extension.
    """
    global MIME_TYPES
    ext = os.path.splitext(ruta_archivo)[1].lower()
    return MIME_TYPES.get(ext, "application/octet-stream")


# Declaramos el diccionario global que albergará los estados HTTP (Ej: 200 => "OK")
HTTP_STATUSES = {}

def http_statuses_init():
    """
    Inicializa el mapa de estados HTTP trayendo el catálogo oficial de la librería estándar de Python.
    """
    global HTTP_STATUSES
    try:
        # Importamos el enumerador nativo de Python
        HTTPStatus = http_module.HTTPStatus
        
        # Recorremos el enumerador para extraer cada código y su frase descriptiva
        for status in HTTPStatus:
            codigo = status.value
            frase = status.phrase
            HTTP_STATUSES[codigo] = frase
        
    except Exception as e:
        print(f"⚠️ Alerta: No se pudo cargar HTTPStatus de Python, usando defaults mínimos: {e}", file=sys.stderr, flush=True)
        # Mapeo mínimo de contingencia por si el puente de CPython falla al arrancar
        HTTP_STATUSES[200] = "OK"
        HTTP_STATUSES[400] = "Bad Request"
        HTTP_STATUSES[403] = "Forbidden"
        HTTP_STATUSES[404] = "Not Found"
        HTTP_STATUSES[500] = "Internal Server Error"
        HTTP_STATUSES[501] = "Not Implemented"

http_statuses_init()

async def send_error_response(status_code, scope, send, 
    msg="OxiServer was unable to process this request on the local runtime layer."):
    """
    Dispatches a beautifully styled Nginx-like HTML error page to the client socket.
    Maintains the precious monospace aesthetics established in the directory lister.
    """
    
    status_phrase = HTTP_STATUSES.get(status_code, "Error")
    
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
                <b>Client IP:</b> {to_bytes(scope['client'][0]).decode('latin-1')}<br>
                <b>Request:</b> {scope['method']} {scope['path']} {scope.get('protocol', 'HTTP/1.1')}<br>
                <b>Server Timestamp:</b> {get_styled_date()}
            </div>
        </div>
        <div class="footer">OxiServer/{CONFIG["version"]} (C++/Julia Powered ASGI Engine)</div>
    </body>
    </html>
    """
    
    html_bytes = to_bytes(html_error_payload)
    payload_length = len(html_bytes)

    try:
        headers = [
            (b'content-type', b'text/html; charset=utf-8'),
            (b'content-length', to_bytes(payload_length))
            ]
        # 1. Send the ASGI response start event (Headers)
        await send({
            'type': 'http.response.start',
            'status': status_code,
            'headers': headers
        })
        
        # 2. Send the ASGI response body event
        await send({
            'type': 'http.response.body',
            'body': html_bytes,
            'more_body': False
        })
        
    except: 
        pass
        # Fail silently if the socket pipe was dropped by the client browser
    
def is_mp4(web_path: str) -> bool:
    """
    Determina si el recurso solicitado corresponde a un video MP4 basado en su extensión física.
    """
    global CONFIG
    local_file_path = os.path.join(os.getcwd(), CONFIG["static_dir"], web_path.lstrip('/'))
    ext = os.path.splitext(local_file_path)[1].lower()
    return os.path.isfile(local_file_path) and ext == ".mp4"

def is_static_file(ruta_web:str):
    # CONFIG["static_dir"] maps to your "static" folder from config.json
    local_route = os.path.join(os.getcwd(), CONFIG["static_dir"], ruta_web.lstrip('/'))
    return os.path.isfile(local_route)

def is_cgi_app(ruta_web: str):
    """
    b2-1) Determines if the file is a CGI application based on extension or path.
    """
    local_route = os.path.join(os.getcwd(), CONFIG["static_dir"], ruta_web.lstrip('/'))
    # print(f"RUTA_LOCAL: {local_route}")
    
    # ✅ CORRECCIÓN: Construimos el segmento y validamos si está presente en la ruta física
    cgi_folder_segment = "/" + CONFIG.get("cgi_dir", "cgi-bin").strip("/") + "/"
    has_cgi_directory = cgi_folder_segment in local_route
    
    # Extensiones ejecutables
    ext = os.path.splitext(local_route)[1].lower()
    is_cgi_extension = ext in (".py", ".sh", ".cgi", ".pl", ".rb", ".java")
    
    # Solo es una app CGI si está dentro de la carpeta cgi-bin O tiene una extensión CGI legítima
    return os.path.isfile(local_route) and (has_cgi_directory or is_cgi_extension)

def is_static_resource(ruta_web:str):
    """
    b) Determines if a requested web resource exists physically inside the configured static directory.
    """
    local_route = os.path.join(os.getcwd()   , CONFIG["static_dir"], ruta_web.lstrip('/'))
    return os.path.isfile(local_route) or os.path.isdir(local_route)

def is_dir_resource(ruta_web:str):
    """
    b2) Determines if the local static path is a directory.
    """
    local_route = os.path.join(os.getcwd(), CONFIG["static_dir"], ruta_web.lstrip('/'))
    return os.path.isdir(local_route)

def is_php(web_path: str) -> bool:
    """
    b2-3) Determines if the requested file corresponds to a PHP script based on its extension.
    """
    local_file_path = os.path.join(os.getcwd(), CONFIG["static_dir"], web_path.lstrip('/'))
    ext = os.path.splitext(local_file_path)[1].lower()
    return os.path.isfile(local_file_path) and ext == ".php"

# 1. Función síncrona simplificada: solo lee del puntero actual del archivo
def _read_chunk_sync(fp, offset, chunk_size):
    fp.seek(offset)
    return fp.read(chunk_size)

def read_file_chunk(file_path, offset, chunk_size):
    with open(file_path, 'rb') as fp:
        fp.seek(offset)
        return fp.read(chunk_size)

async def read_file_in_chunks(file_path, 
                              chunk_size=CONFIG.get('chunk_size', 8192), 
                              initial_offset=0,
                              total_len=None):
    loop = asyncio.get_running_loop()
    offset = initial_offset
    if not total_len:
        total_len = os.path.getsize(file_path)
    bytes_read = 0
    with ThreadPoolExecutor(max_workers=1) as executor:
        fp = await loop.run_in_executor(executor, open, file_path, 'rb')
        # with open(file_path, 'rb') as fp:
        with fp:
            while True:
                chunk = await loop.run_in_executor(executor, _read_chunk_sync, fp, offset, 
                                                min(chunk_size, (total_len - bytes_read)))
                if not chunk:
                    break
                # chunks.append(chunk)
                yield chunk
                await asyncio.sleep(0)
                bytes_read += len(chunk)
                if bytes_read >= total_len:
                    break
                offset += len(chunk)

async def handle_cgi(scope, receive, send):

    cgipath = f"{os.path.join(os.getcwd(), CONFIG.get('static_dir', 'static'))}{scope.get('path')}"
    request_body = b''
    if scope.get('method', 'get').upper() in ["PUT", "POST", "PATCH"]:
        try:
            post_dict = await asyncio.wait_for(receive(), timeout=1.0)
            request_body = post_dict.get("body", b'')
        except asyncio.TimeoutError:
            request_body = b''

    async def actually_send_cgi(*args):
        newd = dict(scope['headers'])
        environ = {}
        environ['GATEWAY_INTERFACE'] = f'CGI/{scope["http_version"]}'
        environ["SERVER_SOFTWARE"] = f"OxiServer/{CONFIG['version']} (Julia-Powered)"
        environ['SERVER_NAME'] = scope['server_name']
        environ['SERVER_PORT'] = scope['local_port']
        environ['REMOTE_HOST'] = scope['remote-host']
        environ['REMOTE_PORT'] = scope['remote-port']
        environ['QUERY_STRING'] = scope['query_string'].decode('utf-8')
        environ['CGI_PATH'] = scope['path']
        environ['SCRIPT'] = os.path.split(scope['path'])[1]
        environ['X-REAL-IP'] = scope.get('x-real-ip', '127.0.0.1')
        environ["REQUEST_METHOD"] = scope["method"].upper()
        environ["CONTENT_LENGTH"] = str(len(request_body))
        environ["CONTENT_TYPE"] = newd.get(b"content-type", b"application/x-www-form-urlencoded").decode('latin-1')

        for [k, v] in scope.get("headers", []):
            key = k.decode('latin-1').upper().replace('-', '_')
            if key == 'CONTENT_TYPE':
                environ['CONTENT_TYPE'] = v.decode('latin-1')
            environ[f'HTTP_{key}'] = v.decode('latin-1')

        pipe = asyncio.subprocess.PIPE
        process = None
        if len(args) == 0:
            return await send_error_response(500, scope, send, msg="No CGI executable specified")
        elif len(args) == 1:
            try: 
                process = await asyncio.create_subprocess_exec(args[0], stdin=pipe, stdout=pipe, stderr=pipe, env=environ)
            except Exception as exc:
                excname = exc.__class__.__name__
                return await send_error_response(500, scope, send, msg=f"Couldn't create CGI Process due to {excname}: {exc}")
        else:
            try:
                process = await asyncio.create_subprocess_exec(args[0], args[1], stdin=pipe, stdout=pipe, stderr=pipe, env=environ)
            except Exception as exc:
                excname = exc.__class__.__name__
                return await send_error_response(500, scope, send, msg=f"Couldn't create CGI Process due to {excname}: {exc}")
        out, _ = await process.communicate(request_body)
        io_out = io.BytesIO(out)
        code = 200
        headers = [(b'connection' , b'close')]
        body= b''
        has_content_length = False
        has_content_type = False

        resp_line = io_out.readline().rstrip(b'\r\n').strip()
        try:
            _, code, _ = resp_line.split(b' ', 3)
            if code.decode().isnumeric():
                code = int(code)
                resp_line = io_out.readline().rstrip(b'\r\n').strip()
            else:
                code = 200
        except Exception as exc:
            pass
            # await log_msg(f"Se produjo un error de tipo '{exc.__class__.__name__}': {exc}")
        while len(resp_line):
            if b': ' in resp_line:
                k, v = list(map(lambda t: t.lower().strip(), resp_line.split(b': ')))
                if k == b'content-type':
                    has_content_type = True
                elif k == b'content-length':
                    has_content_length = True
                headers.insert(0, (k, v))
                resp_line = io_out.readline().rstrip(b'\r\n').strip()
            else: 
                body += resp_line
                break

        body += io_out.read()
        if not has_content_type:
            headers.insert(0, (b'content-type', b'text/html; charset=utf-8'))
        if not has_content_length:
            headers.insert(0, (b'content-length', str(len(body)).encode('latin-1')))
        
        startdict = { 
            'type': 'http.response.start',
            'status': code,
            'headers': headers
        }
        bodydict = {
            'type': 'http.response.body',
            'body': body,
            'more_body': False
        }
        await send(startdict)
        await send(bodydict)

    interpreter = ""
    if CONFIG.get('allow_cgi'):
        if await asyncio.to_thread(os.path.isfile, cgipath): 
            if await asyncio.to_thread(os.access, cgipath, os.X_OK):
                return await actually_send_cgi(cgipath)
            else:
                ext = os.path.splitext(cgipath)[1]
                if ext == ".py":
                    interpreter = "python3"
                elif ext == ".sh":
                    interpreter = "bash"
                elif ext == ".pl":
                    interpreter = "perl"
                elif ext == ".rb":
                    interpreter = "ruby"
                elif ext == ".java":
                    interpreter = "java"
                else:
                    # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
                    return await send_error_response(403, scope, send, msg=os.path.split(cgipath)[1])
                return await actually_send_cgi(interpreter, cgipath)
        else:
            # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
            return await send_error_response(403,  scope, send, msg=os.path.split(cgipath)[1])
    else:
        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
        return await send_error_response(403,  scope, send, os.path.split(cgipath)[1])

async def handle_php(scope, receive, send):
    if not PHP_BINARY_PATH:
        return await send_error_response(500, scope, send, msg="PHP binary not present in this system")

    phppath = f"{os.path.join(os.getcwd(), CONFIG.get('static_dir', 'static'))}{os.path.sep}{scope.get('path')}"
    request_body = b''
    if scope.get('method', 'get').upper() in ["PUT", "POST", "PATCH"]:
        try:
            # post_bytes = await asyncio.wait_for(reader.read(), timeout=1.0)
            post_dict = await asyncio.wait_for(receive(), timeout=1.0)
            request_body = post_dict.get("body", b'')
        except asyncio.TimeoutError:
            post_bytes = b''

    async def actually_send_php():
        newd = dict(scope.get("headers"))
        php_env = {
            "SERVER_SOFTWARE": f"OxiServer/{CONFIG['version']} (Julia-Powered)",
            "SERVER_NAME": "localhost",
            "GATEWAY_INTERFACE": "CGI/1.1",
            "SERVER_PROTOCOL": scope["protocol"],
            "PATH_INFO"      : scope["path"],
            "SCRIPT_NAME"    : scope["path"],
            "SCRIPT_FILENAME": phppath, # Absolute physical filesystem target
            #SCRIPT_FILENAME": scope["path"].lstrip("/"), # Absolute physical filesystem target
            "REDIRECT_STATUS": "200",                     # Mandatory bypass safety switch for php-cgi
            "QUERY_STRING"   : scope["query_string"],
            "REMOTE_ADDR"    : scope["client"][0],
            "REQUEST_METHOD" : scope["method"].upper(),
            "CONTENT_LENGTH" : str(len(request_body)),
            "CONTENT_TYPE"   : newd.get(b"content-type", b"application/x-www-form-urlencoded").decode('latin-1')
        }


        for [k, v] in scope.get("headers", []):
            key = k.decode('latin-1').upper().replace('-', '_')
            if key == 'CONTENT_TYPE':
                php_env['CONTENT_TYPE'] = v.decode('latin-1')
            #print(f"Setting HTTP_{key} to {v.decode('utf-8')}")
            php_env[f'HTTP_{key}'] = v.decode('latin-1')

        pipe = asyncio.subprocess.PIPE
        process = await asyncio.create_subprocess_exec(str(PHP_BINARY_PATH), phppath, stdin=pipe, stdout=pipe, stderr=pipe, env=php_env)
        if process.stdin == None:
            return await send_error_response(500, scope, send, msg="Error while launching PHP process.")
        try:
            process.stdin.write(request_body)
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()
        except Exception as exc:
            excname = exc.__class__.__name__
            await log_msg(f"{get_styled_date()} - {excname} while writing to PHP stdin: {exc}", fp=sys.stderr)
        out, _ = await process.communicate()
        
        io_out = io.BytesIO(out)
        code = 200
        headers = [(b'connection' , b'close')]
        body= b''
        has_content_length = False
        has_content_type = False

        resp_line = io_out.readline().rstrip(b'\r\n').strip()
        try:
            _, code, _ = resp_line.split(b' ', 3)
            if code.decode().isnumeric():
                code = int(code)
                resp_line = io_out.readline().rstrip(b'\r\n').strip()
            else:
                code = 200
        except Exception as exc:
            pass
            # await log_msg(f"Se produjo un error de tipo '{exc.__class__.__name__}': {exc}")
        while len(resp_line):
            if b': ' in resp_line:
                k, v = list(map(lambda t: t.lower().strip(), resp_line.split(b': ')))
                if k == b'content-type':
                    has_content_type = True
                elif k == b'content-length':
                    has_content_length = True
                headers.insert(0, (k, v))
                resp_line = io_out.readline().rstrip(b'\r\n').strip()
            else: 
                body += resp_line
                break

        body += io_out.read()
        if not has_content_type:
            headers.insert(0, (b'content-type', b'text/html; charset=utf-8'))
        if not has_content_length:
            headers.insert(0, (b'content-length', str(len(body)).encode('latin-1')))
        
        startdict = { 
            'type': 'http.response.start',
            'status': code,
            'headers': headers
        }
        bodydict = {
            'type': 'http.response.body',
            'body': body,
            'more_body': False
        }
        await send(startdict)
        await send(bodydict)

    if CONFIG.get('allow_cgi'):
        if await asyncio.to_thread(os.path.isfile, phppath): 
            return await actually_send_php()
        else:
            # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
            return await send_error_response(404,  scope, send, msg=f"{os.path.split(phppath)[1]} is not a PHP file.")
    else:
        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
        return await send_error_response(403,  scope, send, os.path.split(phppath)[1])


def get_header(scope, key):
    for k, v in scope["headers"]:
        if k.lower() == to_bytes(key.lower()):
            return k, v
    return None

def range_header(scope):
    return get_header(scope, "range")

async def handle_any_file(scope, send):
    filename = os.path.join(os.getcwd(), CONFIG["static_dir"], scope["path"].lstrip('/'))
    filesize = os.path.getsize(filename)
    filetype = get_mime_type(filename)
    charset = ";charset=utf-8" if filetype.startswith('text') else "" 
    chunksize = CONFIG['chunk_size']
    offset_start = 0
    offset_end = filesize - 1
    bytes_to_send = offset_end - offset_start + 1

    headers = [
        (b'content-type', f"{filetype}{charset}".encode('latin-1')),
    ]

    status = 200

    rangeheader = range_header(scope)
    if rangeheader:
        rangeh = rangeheader[1].replace(b"bytes=", b"")
        points = list(map(lambda s: s.decode('latin-1'), rangeh.split(b'-')))
        points = list(map(lambda val: int(val) if len(val) else filesize -1, points))
        offset_start = points[0]
        offset_end = points[1]
        bytes_to_send = offset_end - offset_start + 1
        headers.append((b'content-length', f"{bytes_to_send}".encode('latin-1')))
        headers.append((b"content-range",  f"bytes {offset_start}-{offset_end}/{filesize}".encode('latin-1')))
        headers.append((b'accept-ranges', b'bytes'))
        # await log_msg(f"Has range header: {points}")
        status = 206
    else:
        headers.append((b'content-length', f"{filesize}".encode('latin-1')))

    headers.append((b'connection', b'close'))

    startdict = {'type': 'http.response.start', 'status': status, 'headers': headers}
    try:
        await send(startdict)
    except:
        return

    async for chunk in read_file_in_chunks(filename, chunksize, offset_start, bytes_to_send):
        d = {'type': 'http.response.body', 'body': chunk, 'more_body': True}
        try:
            await send(d)
        except Exception as exc:
            excname = exc.__class__.__name__
            # await log_msg(f"{excname} occurred while trying to send body chunk: {exc}")
            return
        
    try:
        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
    except:
        return

    #  return await send_error_response(501, scope, send, msg="Universal file handler in construction.")

async def handle_send_dir(scope, send):
    sep = os.path.sep
    web_path = scope["path"]
    local_dir_path = os.path.join(os.getcwd(), CONFIG["static_dir"], web_path.lstrip('/'))

    if not os.path.isdir(local_dir_path):
        await send_error_response(400, scope, send,
        msg="<strong>$(web_path)</strong> is not a directory.")
        return

    try:
        # --- EXPLICIT SECURITY FIREWALL (CGI Directory Protection) ---
        # Aseguramos que cgi_dir tenga un valor por defecto consistente
        cgi_dir_name = CONFIG.get("cgi_dir", "cgi-bin").strip("/")
        
        # Si la ruta web apunta exactamente al directorio CGI o empieza con él seguido de una barra
        if web_path.strip("/") == cgi_dir_name or web_path.startswith(f"/{cgi_dir_name}/"):
            
            # Corrección del log_msg: Evitamos el .decode() si scope['client'][0] ya viene como string
            client_data = scope.get('client')
            ip_address = client_data[0] if client_data else "127.0.0.1"
            if isinstance(ip_address, bytes):
                ip_address = ip_address.decode('latin-1')
                
            await log_msg(f"⚠️ Security Alert: Blocked directory listing attempt on CGI folder from {ip_address}")
            await send_error_response(403, scope, send,
            msg=f"<strong>{web_path}</strong> listing is forbidden.")
            return

        # Native high-performance directory indexing from the OS kernel
        directory_contents = os.listdir(local_dir_path)
        dirs = sorted(filter(lambda f: Path(f"{local_dir_path}{sep}{f}").is_dir(), directory_contents))
        files = sorted(filter(lambda f: Path(f"{local_dir_path}{sep}{f}").is_file(), directory_contents))
        directory_contents = (*dirs, *files)

        # Normalize the web path path display for the HTML header
        display_path =  "/" if web_path == "" else web_path
        display_path = f"{display_path.rstrip('/')}/"

        # 1. Start crafting the dynamic Nginx-style HTML payload
        html_payload = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Index of {display_path}</title>
            <style>
                body {{ font-family: 'monospace', sans-serif; margin: 2rem; background: #fafafa; color: #111; }}
                h1 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; font-size: 1.5rem; }}
                ul {{ list-style: none; padding-left: 0; }}
                li {{ margin: 0.4rem 0; }}
                a {{ color: #0066cc; text-decoration: none; font-size: 1.1rem; }}
                a:hover {{ text-decoration: underline; }}
                .footer {{ margin-top: 2rem; border-top: 1px solid #ccc; padding-top: 0.5rem; font-size: 0.9rem; color: #555; }}
            </style>
        </head>
        <body>
            <h1>Index of {display_path}</h1>
            <ul>
        """

        # Inject a "Parent Directory" link if the user is inside a subfolder
        if display_path != "/":
            # Cleanly calculate the parent URI path slice
            # parent_path = f"{os.path.split(web_path.rstrip('/'))[0]}"
            parent_path = os.path.dirname(web_path.rstrip('/'))
            html_payload += f"<li><a href=\"{parent_path}{'/' if parent_path != '/' else ''}\">📁 .. (Parent Directory)</a></li>"

        # 2. Iterate over the filesystem items and append links to the layout
        
        for item in directory_contents:
            # Skip hidden files starting with a dot (like .git, .env) for basic security
            if item.startswith("."):
                continue
            
            # Determine item visual icon badge by testing physical attributes
            full_item_path = os.path.join(local_dir_path, item)
            icon_badge = "📁" if os.path.isdir(full_item_path) else "📄"
            
            # Web browsers require directory links to terminate with a trailing slash
            item_link = item + "/" if os.path.isdir(full_item_path)  else item
            
            html_payload += f"<li>{icon_badge} <a href=\"{display_path}{item_link}\">{item}</a></li>"

        # Append closing layout wrappers and signature metrics
        html_payload += f"""
            </ul>
            <div class="footer">OxiServer/{CONFIG["version"]} (C++/Julia Powered ASGI Engine)</div>
        </body>
        </html>
        """

        html_bytes = html_payload.encode('utf-8')
        payload_length = len(html_bytes)

        # 3. Emit official HTTP/1.1 response packages down the pipe
        headers = [
            (b"content-type",  b"text/html; charset=utf-8"),
            (b"content-length",  f"{payload_length}".encode("latin-1")),
            (b"connection", b"close")
        ]
        startdict = {'type': 'http.response.start', 'status': 200, 'headers': headers}
        bodydict = {'type': 'http.response.body', 'body': html_bytes, 'more_body': False}
        await send(startdict)
        await send(bodydict)

    except Exception as e:
        pass


    # await send_error_response(501, scope=scope, send=send, msg=f"Directory listing for <strong>{scope['path']}</strong> is not yet implemented.<br>Coming soon!")



#==================================================================================================

async def static_app(scope, receive, send):
    global CONFIG, HTTP_STATUSES, MIME_TYPES, PHP_BINARY_PATH, staticdir

    if scope['type'] != 'http':
        await send_error_response(400, scope, send, 
                                  msg="OxiServer only supports HTTP requests in this static app.")
        return

    if scope['path'] == "/":
        for index_file in CONFIG["index_files"]:
            if is_static_file(f"/{index_file}"):
                if is_cgi_app(f"/{index_file}"):
                    await send_error_response(403, scope=scope, send=send, msg=f"CGI execution forbidden outside of cgi directory.")
                    # await send_error_response(501, scope=scope, send=send, msg=f"CGI execution for <strong>{scope['path']}</strong> is not yet implemented.")
                elif is_php(f"/{index_file}"):
                    scope["path"] = f"/{index_file}"
                    await handle_php(scope, receive, send)
                else:
                    #await send_error_response(501, scope=scope, send=send, msg=f"File delivery for <strong>{scope['path']}</strong> is not yet implemented.")
                    scope["path"] = f"/{index_file}"
                    #await handle_send_file(scope, send)
                    await handle_any_file(scope, send)
                return

        if (CONFIG["allow_dirlisting"] and is_static_resource("/")):
            if len(CONFIG["static_dir"]): 
                await send_error_response(501, scope=scope, send=send, msg=f"Directory listing for <strong>{scope['path']}</strong> is not yet implemented.")
                return
            else:
               await handle_send_dir(scope, send)
        else:    
            await send_error_response(404, scope=scope, send=send, msg=f"Resource <strong>{scope['path']}</strong> not found.")

    if is_static_resource(scope["path"]):
        
        # b2) Is it a directory?
        if is_dir_resource(scope["path"]):
            # b2-2) If dirlisting is allowed, handle it; else, return 403 Forbidden
            if CONFIG["allow_dirlisting"]:
                await handle_send_dir(scope, send)
                # await send_error_response(501, scope=scope, send=send, msg=f"Directory listing for <strong>{scope['path']}</strong> is not yet implemented.")
            else:
                await send_error_response(403, scope=scope, send=send, msg="Directory listing not allowed with current configuration.")
            return
        else:
            # b2-1) Not a directory. Is it a CGI application?
            if is_cgi_app(scope["path"]):
                # b2-1-2) If cgi is allowed, execute it; else, return 403 Forbidden
                if CONFIG["allow_cgi"]:
                    await handle_cgi(scope, receive, send)
                    # await send_error_response(501, scope=scope, send=send, msg="CGI handling not yet implemented.")
                else:
                    await send_error_response(403, scope=scope, send=send, msg="CGI handling not allowed with current configuration.")
            # ─── NUEVA ADUANA DE PHP DIRECTA ─────────────────────────────────
            elif is_php(scope["path"]):
                # OxiServer catches PHP directly out of the box
                # await send_error_response(501, scope=scope, send=send, msg="PHP handling not yet implemented.")
                await handle_php(scope, receive, send)
                return
            else:
                # b2-1-1) Not a CGI, it's a traditional static asset file
                # await send_error_response(501, scope=scope, send=send, msg="File sending not yet implemented.")
                # await handle_send_file(scope, send)
                await handle_any_file(scope, send)
            return
    await send_error_response(404, scope=scope, send=send, msg=f"Resource <strong>{scope['path']}</strong> not found.")


def main():
    global static_app
    import subprocess
    try:
        from server import run
    except Exception as exc:
        excname = exc.__class__.__name__
        print(f"{excname}: {exc}")
        raise
    app = static_app
    subprocess.run('clear')
    CONFIG["static_dir"] = ""
    run(app, "0.0.0.0", 8086)

if __name__ == "__main__":
    main()
