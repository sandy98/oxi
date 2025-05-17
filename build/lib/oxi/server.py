# -*- coding: utf-8 -*-

import asyncio, os, random, subprocess, re, mimetypes, errno, signal, hashlib, time
from threading import Thread
from typing import Callable
from pprint import pprint
from pathlib import Path
from time import time as timestamp, strftime as tstrftime, strptime as tstrptime
from datetime import datetime as dt
from urllib.parse import urlparse, parse_qsl, unquote_plus
from functools import wraps

try:
    from . import  __version__ as oxi_version, __oxi_port__ as oxi_port, __oxi_host__ as oxi_host
    from .config import Config
    from .utils import (is_windows, is_linux, is_mac, 
                        http_status_dict as status_dict, to_bytes, no_ctrlc_echo)
    from .mp4parser import Mp4
except ImportError:
    from activate_this import oxi_env
    if not oxi_env:
        raise ImportError("Oxi environment not activated. Please activate the virtual environment.")
    from oxi import  __version__ as oxi_version, __oxi_port__ as oxi_port, __oxi_host__ as oxi_host
    from oxi.config import Config
    from oxi.utils import (is_linux, is_windows, is_mac, 
                           http_status_dict as status_dict, to_bytes, no_ctrlc_echo)
    from oxi.mp4parser import Mp4

async def is_static(resource:str) -> bool:
    """
    Check if the resource exists in the file system.
    """
    return await asyncio.to_thread(os.path.exists, resource)

async def is_file(resource:str) -> bool:
    """
    Check if the resource is a regular file.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    return exists and await asyncio.to_thread(os.path.isfile, resource)

async def is_dir(resource:str) -> bool:
    """
    Check if the resource is a directory.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    return exists and await asyncio.to_thread(os.path.isdir, resource)

async def is_exe(resource:str) -> bool:
    """
    Check if the resource is an executable file.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    return exists and (await asyncio.to_thread(os.access, resource, os.X_OK))

async def is_cgi_exe(resource:str, cgi_dir:str="cig-bin") -> bool:
    """
    Check if the resource is a CGI executable.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    if not exists:
        return False
    is_exec = await is_exe(resource)
    if not is_exec:
        return False
    if not cgi_dir in resource:
        return False
    return True

async def finalize_writer(writer):
    try:
        # writer.write(b"\r\n\r\n")
        await writer.drain()
    except Exception as e:
        print(f"Writer drain error: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"Writer close error: {e}")

enctypes: tuple = (b"application/x-www-form-urlencoded", 
                   b"multipart/form-data", 
                   b"application/json",
                   b"text/plain")

strftime_template = "%a, %d  %b %Y %X %Z"

original_zen = """Gur Mra bs Clguba, ol Gvz Crgref

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

zen = """
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


class ProtocolFactory: 
    """
    ProtocolFactory class to handle the server protocol.
    """
    
    success_line = "HTTP/1.1 200 OK\r\n"
    partial_line = "HTTP/1.1 206 Partial Content\r\n"
    bad_request_line = "HTTP/1.1 400 Bad Request\r\n"
    not_implemented_line = "HTTP/1.1 501 Not Implemented\r\n"
    forbidden_line = "HTTP/1.1 403 Forbidden\r\n"
    moved_line = "HTTP/1.1 301 Moved Permanently\r\n"
    moved_temporary_line = "HTTP/1.1 302 Moved Temporarily\r\n"
    error_line = "HTTP/1.1 500 Internal Server Error\r\n"
    not_found_line = "HTTP/1.1 404 Not Found\r\n"

    @property
    def base_dir(self) -> str:
        if not os.path.exists(self._base_dir):
            self._base_dir = ''
        return f"{os.path.sep}{self._base_dir}"

    @base_dir.setter
    def base_dir(self, value: str) -> None:
        if os.path.exists(value):
            self._base_dir = value
        else:
            raise ValueError(f"Base directory '{value}' does not exist.")

    @property
    def full_base_dir(self) -> str:
        return f"{self.cwd}{self.base_dir}"

    async def has_index(self):
        candidates = self.index_files if hasattr(self, 'index_files') else ['index.html', 'index.htm']
        full_candidates = [os.path.join(self.full_base_dir, f) for f in candidates]
        for candidate in full_candidates:
            if await is_file(candidate):
                return True, candidate
        return False, None
    
    def __init__(self, app: Callable = None, *, base_dir: str = None):
        self.app = app
        if self.app:
            self.app._protocol = self
        self.cwd = os.getcwd()

        for k in Config.keys():
            setattr(self, k, Config[k])
        
        self._base_dir = base_dir or (self.static_dir if hasattr(self, 'static_dir') else 'static')
        self.version = oxi_version
        self.zen = zen
        self.original_zen = original_zen
        self.strftemplate = strftime_template
        self.enctypes = enctypes

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle the incoming request and send a response.
        """
        try:
            method, path, protocol = await self.get_request_line(reader)
            parsed = urlparse(path)
            path = parsed.path
            query = parsed.query
            if query:
                query = dict(parse_qsl(query))
            else:
                query = {}
            netloc = parsed.netloc

        except ValueError as e:
            print(f"Error parsing request line: {e}")
            return await self.send_status_response(writer, status_code=400, msg=str(e))
        print(f"Received request: {method} {path} {protocol}")
        if method not in ["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"]:
            msg = f"Method {method} not allowed."
            print(msg)
            return await self.send_status_response(writer, status_code=405, msg=msg)

        try:
            request_headers_block= await self.get_headers_block(reader)
            # print(f"\nHeaders block:\n{request_headers_block.decode('utf-8')}\n\n")
        except ValueError as e:
            print(f"Error parsing  request headers: {e}")
            return await self.send_status_response(writer, status_code=400, msg=str(e))
        request_headers = await self.parse_headers(request_headers_block)
        # print("@")
        # pprint(request_headers, indent=4, compact=False, width=40, sort_dicts=False)
        # print("@")
        if path == "/oxiserver_demo" and method == "GET":
            print(f"Serving Oxi Server demo page.")
            return await self.oxiserver_demo(writer=writer)
        else:
            fullpath = os.path.join(self.full_base_dir, path.lstrip("/").replace("/", os.path.sep)) 
            if await is_file(fullpath):
                if not await is_cgi_exe(fullpath, self.cgi_dir):
                    if method == "GET":
                        print(f"Serving file: {fullpath}")
                        return await self.send_file(writer=writer, fullpath=fullpath, headers=request_headers)
                    else:
                        print(f"Method {method} not allowed for file: {fullpath}")
                        return await self.send_status_response(writer, status_code=405, msg=f"Method {method} not allowed for file.")  
                else:
                    print(f"Serving CGI executable: {fullpath}")
                    return await self.send_file(writer=writer, fullpath=fullpath, headers=request_headers)
            elif path == "/":
                exists, index_file = await self.has_index()
                if exists:
                    print(f"Serving index file: {index_file}")
                    return await self.send_file(writer=writer, fullpath=index_file, headers=request_headers)
                else:
                    if not self.allow_dirlisting:
                        print(f"Directory listing not allowed: {fullpath}")
                        return await self.send_status_response(writer, status_code=403, msg="Directory listing not allowed.")
                    print(f"Serving static directory: {self.static_dir}")
                    return await self.send_directory(writer, path=path, dirpath=self.full_base_dir)
            elif await is_dir(fullpath):
                if not self.allow_dirlisting:
                    print(f"Directory listing not allowed: {fullpath}")
                    return await self.send_status_response(writer, status_code=403, msg="Directory listing not allowed.")
                print(f"Serving directory: {fullpath}")
                return await self.send_directory(writer, path=path, dirpath=fullpath)
            else:
                if self.app is not None:
                    print(f"Serving app: {self.app.name}")
                    return await self.app(reader=reader, writer=writer)
                else:
                    print(f"File {path} not found.")
                    return await self.send_status_response(writer, status_code=404, msg=f"Resource '{path}' not found.")  

    @classmethod
    async def send_directory(cls, writer: asyncio.StreamWriter, path: str, dirpath: str):
        
        async def get_file_details(entry):
            fullpath = dirpath + os.path.sep + entry
            size = await asyncio.to_thread(os.path.getsize,fullpath)
            ret = f'<span style="text-align: right;" class="black">{size:,} bytes</span>'
            return ret
        
        pth = Path(path.strip('/'))
        prevdir = ("/" + str(pth.parent)) if path != '/' else '/'
        body = f"""
            <!DOCTYPE html>
            <html><head><title>Directory Listing</title>
            <style>
                body {{
                    background-color: #f0f0f0;
                    font-family: Helvetica, Arial, sans-serif;
                    font-size: 16px;
                }}
                .green {{
                    color: green;
                }}
                .silver {{
                    color: silver;
                }}
                .black {{
                    color: black;
                }}
                .renglon_dirlist {{
                    margin-left: 1em;
                    width: 50%;
                    max-width: 50%;
                    display: flex;
                    flex-direction: row;
                    justify-content: space-between;
                    align-items: center;
                    list-style-type: none;
                    font-size: 150%;
                    margin-bottom: 0.5em;
                }}
                a.link {{
                    text-decoration: none;
                    color: steelblue;
                    font-weight: bold;
                }}
                a.link:hover {{
                    color: black;
                }}
                @media (max-width: 798px) {{
                    .renglon_dirlist {{
                        width: 90%;    
                        max-width: 90%;
                    }}
                }}
            </style>
            </head><body style="margin-left: 1em; margin-right: 1em;">
            <h2>Directory listing for <span class="green">.{str(path)}</span></h2></hr>
            <hr>
            <p style="margin-bottom: 1em; text-align: center; font-family: Times New Roman; font-size: 16px;">Oxi/{oxi_version}</p>
            <hr>
            <ul>
                <li class="renglon_dirlist"><a class="link" title="Home" href="/">.</a></li>
                <li class="renglon_dirlist"><a class="link" title="{str(prevdir)}" href="{str(prevdir)}">..</a></li>
        """
        entries = await asyncio.to_thread(os.listdir, dirpath)
        entries.sort()
        entries.sort(key=lambda e: os.path.isdir(dirpath + os.path.sep + e), reverse=True)
        for entry in entries:
            body += f'''
            <li class="renglon_dirlist">
                <a class="link" href="{path + (os.path.sep if path != '/' else '') + entry}">{entry}</a>
                {'<span class="silver">[DIR]</span>' if (await asyncio.to_thread(os.path.isdir, dirpath + os.path.sep + entry)) else (await get_file_details(entry))}
            </li>'''
        body += "</ul></body></html>"
        body_len = len(body)
        
        # print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")
        
        try:
            writer.write(cls.success_line.encode("utf-8"))
            writer.write(b"content-type: text/html; charset=utf-8\r\n"),
            writer.write(f"content-length: {str(body_len)}\r\n".encode('utf-8'))
            await writer.drain()
        except Exception as e:
            print(f"Error writing directory listing headers: {e}")
            # return await self.send_status_response(writer, status_code=500, reason="Internal Server Error", msg=str(e))
            return
        try:
            writer.write(b"\r\n")
            await writer.drain()
            writer.write(to_bytes(body))
            await writer.drain()
        except Exception as e:
            print(f"Error directory listing writing body: {e}")
            # return await self.send_status_response(writer, status_code=500, reason="Internal Server Error", msg=str(e))

    @classmethod
    async def send_file(cls, writer: asyncio.StreamWriter, fullpath: str, 
                        headers: dict = None, forced: bool = False) -> None:

        content_type = mimetypes.guess_type(fullpath)[0] or "application/octet-stream"
        if content_type == 'video/mp4' and not forced:
            return await cls.send_mp4(writer=writer, fullpath=fullpath, headers=headers)
        file_desc = await asyncio.to_thread(os.open, fullpath, os.O_RDONLY | os.O_NONBLOCK)
        file_stat = await asyncio.to_thread(os.fstat, file_desc)
        body_len = file_stat.st_size
        try:
            writer.write(cls.success_line.encode("utf-8"))
            writer.write(f"Content-Type: {content_type}\r\n".encode("utf-8"))
            writer.write(f"Content-Length: {body_len}\r\n".encode("utf-8"))
            writer.write(b"\r\n")
            await writer.drain()
        except Exception as e:
            print(f"Error writing headers: {e}")
            await asyncio.to_thread(os.close, file_desc)
            # return await self.send_status_response(writer, status_code=500, reason="Internal Server Error", msg=str(e))
            return
        
        async def send_windows():
            remaining = body_len
            while remaining > 0:
                chunk = min(self.chunk_size, remaining)
                try:
                    data = os.read(file_desc, chunk)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
                    remaining -= len(data)
                except BlockingIOError as e:
                    if e.errno == errno.EAGAIN:
                        await asyncio.sleep(0)
                        continue
            await asyncio.to_thread(os.close, file_desc)
            await finalize_writer(writer)

        async def send_linux():
            loop = asyncio.get_running_loop()
            try:
                file_obj = open(file_desc, "rb", closefd=False)
                await loop.sendfile(writer.transport, file_obj)
            except (AttributeError, NotImplementedError, RuntimeError) as e:
                print(f"loop.sendfile() not available or failed ({e}), falling back to read/write")
                return await send_windows()
            await asyncio.to_thread(os.close, file_desc)
            await finalize_writer(writer)

        async def send_mac():
            sock = writer.get_extra_info("socket")
            sock_fd = sock.fileno() 
            offset = 0
            while offset < body_len:
                sent = os.sendfile(sock_fd, file_desc, offset, body_len - offset)
                if sent == 0:
                    break
                offset += sent
            await asyncio.to_thread(os.close, file_desc)
            await finalize_writer(writer)

        if is_windows():
            return await send_windows()
        
        if is_linux():
            # return await send_mac()
            return await send_linux()
        
        if is_mac():
            return await send_mac()

    @classmethod
    async def send_mp4(cls, writer: asyncio.StreamWriter, fullpath: str, headers: dict = None) -> None:
        mp4 = Mp4(fullpath)
        boundaries = await mp4.faststart_boundaries
        response_line = cls.partial_line
        start, end = 0, mp4.filesize - 1

        sec_fetch_dest = headers.get("sec-fetch-dest", None)
        if sec_fetch_dest:
            if sec_fetch_dest != "video":
                response_line = cls.success_line
        bytesrange = headers.get("range")
        if not bytesrange:
            print(f"Range header not found. Sending full file.")
            start = 0
            end = 0
            # boundaries = await mp4.faststart_boundaries
            for entry in boundaries:
                moov_bounds = entry.get('moov')
                if moov_bounds:
                    end = moov_bounds[1] - 1
                    break
            if end == 0:
                end = mp4.filesize - 1
        else:
            bytesrange = bytesrange.lstrip("bytes=")
            start, end = bytesrange.split("-")
            start = int(start)
            end = int(end) if end else mp4.filesize - 1
            if start < 0 or end >= mp4.filesize or start > end:
                print(f"Invalid range: {bytesrange}. Sending full file.")
                start, end = 0, mp4.filesize - 1
        length = end - start + 1
        try:
            writer.write(response_line.encode("utf-8"))
            writer.write(b"Content-Type: video/mp4\r\n")
            writer.write(b"Accept-Ranges: bytes\r\n")
            print(f'\nSENDING video content:\tContent-Range: bytes {start}-{end}/{mp4.filesize}\n')
            writer.write(f'Content-Range: bytes {start}-{end}/{mp4.filesize}\r\n'.encode('utf-8'))                        
            writer.write(f"Content-Length: {length}\r\n\r\n".encode("utf-8"))
            await writer.drain()
        except Exception as e:
            print(f"Error writing mp4 headers: {e}")
            # return await cls.send_status_response(writer, status_code=500, reason="Internal Server Error", msg=str(e))
            return

        stream = mp4.async_stream_range(start, end)
        written = 0
        async for chunk in stream:
            try:
                writer.write(chunk)
                await writer.drain()
                written += len(chunk)
                # print(f"Written {len(chunk)} bytes for a total of {written} out of {mp4.filesize}.")
            except Exception as e:
                print(f"Error writing mp4 chunk: {e}")
                # return await cls.send_status_response(writer, status_code=500, reason="Internal Server Error", msg=str(e))
                break
        try:    
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"Error closing writer: {e}")
            # return await cls.send_status_response(writer, status_code=500, reason="Internal Server Error", msg=str(e))
        finally:
            print(f"{written} bytes written out of {mp4.filesize}.")
            return

    @classmethod    
    async def get_request_line(cls, reader: asyncio.StreamReader) -> tuple[str]:
        """
        Read the request line from the client.
        """
        retries = 0
        max_retries = 3
        while True:
            try:
                request_line = await reader.readuntil(b"\r\n")
                break
            except asyncio.IncompleteReadError as e:
                retries += 1
                print(f"Retrying to read request line: {e}\nAttempt {retries}/{max_retries}")
                if retries >= max_retries:
                    request_line = ''
                    break
                else:
                    await asyncio.sleep(0)
                    continue
        if not request_line:
            raise ValueError("Request line is incomplete after multiple attempts.")
        request_line = request_line.rstrip(b"\r\n")
        if not request_line:
            raise ValueError("Request line is empty after stripping.")
        request_line = request_line.decode("utf-8").strip()
        if not request_line:
            raise ValueError("Request line is empty after decoding.")
        try:
            # self.request_line = request_line
            method, path, protocol = re.split(r"\s+", request_line)
        except ValueError:
            raise ValueError("Request line is malformed. Unable to split into method, path, and protocol.")
        if not method or not path or not protocol:
            raise ValueError("Request line is malformed. Missing method, path, or protocol.")
        return method.upper(), unquote_plus(path), protocol

    @classmethod
    async def get_headers_block(cls, reader: asyncio.StreamReader) -> bytes:
        """
        Read header lines from the client.
        """
        retries = 0
        max_retries = 3
        while True:
            try:
                headers_block = await reader.readuntil(b"\r\n\r\n")
                break
            except asyncio.IncompleteReadError as e:
                retries += 1
                print(f"Retrying to read header blocks: {e}\nAttempt {retries}/{max_retries}")
                if retries >= max_retries:
                    headers_block = b''
                    break
                else:
                    await asyncio.sleep(0)
                    continue
        if not headers_block:
            raise ValueError("Headers block is incomplete after multiple attempts.")
        headers_block = headers_block.rstrip(b"\r\n\r\n")
        if not headers_block:
            raise ValueError("Headers block is empty after stripping.")
        # self.headers_block = headers_block
        return headers_block

    @classmethod
    async def parse_headers(cls, headers_block: bytes) -> dict:
        """
        Parse the headers block into a dictionary.
        """
        headers = {}
        lines = headers_block.decode("utf-8").split("\r\n")
        for line in lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                headers[key.strip().lower()] = value.strip()
        return headers
    
    @classmethod
    async def send_status_response(cls, writer: asyncio.StreamWriter, status_code: int=404, reason: str = None, msg:str="") -> None:
        reason = reason or status_dict.get(status_code, "Unknown Status")
        status_line = f"HTTP/1.1 {status_code} {reason}\r\n"
        writer.write(status_line.encode("utf-8"))
        writer.write(b"Content-Type: text/html\r\n")
        realmsg = msg + '\r\n' if len(msg) else ''
        response = f"""
<html>
<head><title>{status_code} {reason}</title></head>
<body style="background-color: #f0f0f0; font-family: Helvetica, Arial, sans-serif;">
<center><h1>{status_code} {reason}</h1></center>
<hr><center>oxi/{oxi_version}</center>
<p>&nbsp;</p>
<p>{realmsg}</p>
</body>
</html>"""
        # response = f"{status_code} {reason}\r\n{realmsg}\r\n"
        writer.write(f"Content-Length: {len(response)}\r\n\r\n".encode("utf-8"))
        writer.write(response.encode("utf-8"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        
    async def oxiserver_demo(self, writer: asyncio.StreamWriter = None) -> None:
        """
        Send a demo HTML page to the client.
        """
        if writer is None:
            raise ValueError("writer is None. Please provide a valid writer.")
        # Let's begin slowly
        exists = await is_static("./static/img")
        if not exists:
            msg = "Static directory not found. Please create a static directory with images."
            return await self.send_status_response(writer, status_code=404, msg=msg)
        listdir = await asyncio.to_thread(os.listdir, "./static/img")
        listdir = [entry for entry in listdir if mimetypes.guess_type(entry)[0] and mimetypes.guess_type(entry)[0].startswith("image")]
        img_src = random.choice(listdir)
        newzen = random.choice([self.zen, self.zen, self.zen, self.original_zen]).replace("\n", "<br>")
        html = f"""
        <html>
            <head>
                <title>Oxi Server</title>
                <!--<link rel="stylesheet" href="static/css/style.css">-->
            </head>
            <body style="background-color: #f0f0f0; font-size: 120%; font-family: Helvetica, Arial, sans-serif;">
                <div style="text-align: center;">
                    <h1 style="color: steelblue;">Welcome to <strong style="color: red;">Oxi Server</strong>!</h1>
                    <img src="/img/{img_src}" alt="Random Image" width="20%" style="border-radius: 20px;">
                </div>
                <h2>Version: <strong>{self.version}</strong></h2>
                <hr/>
                <p>{newzen}</p>
                <hr>
                <p style="text-align: center;">
                    <a href="/">Home</a>
                </p>
                <hr>
                <p style="text-align: right;ont-size: 16px; margin-right 1em;">Oxi/{oxi_version}</p>
                <script>
                    setInterval(() => location.href = location.href, 10000);
                </script>
            </body>
        </html>
"""
        content_length = len(html)
        print(f"Writing to socket {content_length} bytes.\n")
        content_type = "text/html; charset=utf-8"
        writer.write(self.success_line.encode("utf-8"))
        writer.write(f"Content-Type: {content_type}\r\n".encode("utf-8"))
        writer.write(f"Content-Length: {content_length}\r\n".encode("utf-8"))
        writer.write(b"\r\n")
        writer.write(html.encode("utf-8"))
        writer.write(b"\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

######################################################################################

def fs_monitor():

    parentdir = Path(__file__).parent

    pyfiles = [open(str(entry), 'rb') for entry in parentdir.glob("*.py")]
    hashes = [hashlib.sha1(fd.read()).hexdigest() for fd in pyfiles]

    while True:
        time.sleep(1)
        newpyfiles = [open(str(entry), 'rb') for entry in parentdir.glob("*.py")]
        if len(newpyfiles) != len(pyfiles):
            print(f"File count changed. Signaling server restart")
            time.sleep(0.5)  # Optional debounce
            os.execv(os.sys.executable, [os.sys.executable] + os.sys.argv)            # os.kill(os.getpid(), signal.SIGUSR1)
            # os.kill(os.getpid(), signal.SIGUSR1)
            # return
        newhashes = [hashlib.sha1(fd.read()).hexdigest() for fd in newpyfiles]
        if newhashes != hashes:
            print(f"File hashes changed. Signaling server restart")
            time.sleep(0.5)  # Optional debounce
            os.execv(os.sys.executable, [os.sys.executable] + os.sys.argv)            # os.kill(os.getpid(), signal.SIGUSR1)
            # os.kill(os.getpid(), signal.SIGUSR1)
            # return
        else:
            for fd in newpyfiles:
                fd.close()

######################################################################################

async def run_dev_server(protocol: Callable = ProtocolFactory(), 
                         host:str=oxi_host, port:int=oxi_port, 
                         unix_socket:str=None) -> None:
    
    subprocess.run("clear")

    with no_ctrlc_echo():
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _signal_handler():
            print("\nSignal received. Shutting down...")
            stop_event.set()

    
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        
        server = None
        if unix_socket:
            if os.path.exists(unix_socket):
                os.remove(unix_socket)
            server = await asyncio.start_unix_server(protocol, path=unix_socket, loop=loop)
        else:
            server = await asyncio.start_server(protocol, host, port, reuse_address=True, reuse_port=True)

        server_task = asyncio.create_task(server.serve_forever())

        if unix_socket:
            print(f"\n Oxi Server running at {unix_socket}\n")
        else:
            print(f"\n Oxi Server running at {host}:{port}\n")

        # Wait for shutdown signal
        await stop_event.wait()
        print("Stopping Oxi server...")

        # Cleanup
        server.close()
        await server.wait_closed()
        server_task.cancel()

        try:
            await server_task
        except asyncio.CancelledError:
            pass

        print("Oxi Server shut down cleanly.")

async def runner():
    # protocol = ProtocolFactory()
    # protocol.allow_dirlisting = False
    # await run_dev_server(protocol, host=oxi_host, port=oxi_port)
    await run_dev_server(host=oxi_host, port=oxi_port) # Uses ProtocolFactory() by default

def main():
    # Start the file system monitor in a separate thread
    fs_monitor_thread = Thread(target=fs_monitor, daemon=True)
    fs_monitor_thread.start()
    # Run the server
    asyncio.run(runner())

if __name__ == "__main__":
    main()