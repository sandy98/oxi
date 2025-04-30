# -*- coding: utf-8 -*-

import asyncio, os, random, subprocess, re, mimetypes
from typing import Callable

try:
    from . import  __version__ as oxi_version, __oxi_port__ as oxi_port, __oxi_host__ as oxi_host
    from .utils import dual_mode, is_windows, is_linux, is_unix
except ImportError:
    from activate_this import oxi_env
    if not oxi_env:
        raise ImportError("Oxi environment not activated. Please activate the virtual environment.")
    from oxi import  __version__ as oxi_version, __oxi_port__ as oxi_port, __oxi_host__ as oxi_host
    from oxi.utils import dual_mode, is_linux, is_windows, is_unix

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
    return exists and await asyncio.to_thread(os.access, resource, os.X_OK)

async def is_cgi_exe(resource:str, cgi_dir:str="cig-bin") -> bool:
    """
    Check if the resource is a CGI executable.
    """
    exists = await asyncio.to_thread(os.path.exists, resource)
    if not exists:
        return False
    is_exe = await is_exe(resource)
    if not is_exe:
        return False
    if not cgi_dir in resource:
        return False
    return True

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
    error_line = "HTTP/1.1 500 Internal Server Error\r\n"
    not_found_line = "HTTP/1.1 404 Not Found\r\n"

    @property
    def base_dir(self) -> str:
        if len(self._base_dir) == 0:
            return ''
        return f"{os.path.sep}{self._base_dir}"

    @base_dir.setter
    def base_dir(self, value: str) -> None:
        self._base_dir = value

    @property
    def full_base_dir(self) -> str:
        return f"{os.getcwd()}{self.base_dir}"

    def __init__(self, app: Callable = None, *, base_dir: str = 'static'):
        self.app = app
        if self.app:
            self.app._protocol = self

        self._base_dir = base_dir
        self.version = oxi_version
        self.zen = zen
        self.original_zen = original_zen
        self.strftemplate = strftime_template
        self.enctypes = enctypes
        self.cgi_dir = "cgi-bin"

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle the incoming request and send a response.
        """
        try:
            method, path, protocol = await self.get_request_line(reader)
        except ValueError as e:
            print(f"Error parsing request line: {e}")
            return await self.send_response(writer, status_code=400, reason="Bad Request", msg=str(e))
        print(f"Received request: {method} {path} {protocol}")
        if method not in ["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"]:
            print(f"Method {method} not allowed.")
            writer.write(self.not_found_line.encode("utf-8"))
            writer.write(b"Content-Type: text/plain\r\n")
            response = b"405 Method Not Allowed\r\n\r\n"
            writer.write(f"Content-Length: {len(response)}\r\n\r\n".encode("utf-8"))
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
 
        if method == "GET":
            if path == "/oxiserver_demo":
                print(f"Serving Oxi Server demo page.")
                return await self.oxiserver_demo(writer=writer)
            else:
                fullpath = os.path.join(self.full_base_dir, path.lstrip("/").replace("/", os.path.sep)) 
                if await is_file(fullpath):
                    print(f"Serving file: {fullpath}")
                    return await self.send_file(writer=writer, fullpath=fullpath)
                else:
                    print(f"File not found: {path}")
                    return await self.send_response(writer=writer, status_code=404, reason="Not Found", msg=f"File '{path}' not found.")  
            
    async def send_file(self, writer: asyncio.StreamWriter, fullpath: str) -> None:
        with open(fullpath, "rb") as f:
            data = f.read()
        content_length = len(data)
        mimetype = mimetypes.guess_type(fullpath)[0]
        content_type = mimetype or "application/octet-stream"
        writer.write(self.success_line.encode("utf-8"))
        writer.write(f"Content-Type: {content_type}\r\n".encode("utf-8"))
        writer.write(f"Content-Length: {content_length}\r\n".encode("utf-8"))
        writer.write(b"\r\n")
        await writer.drain()
        writer.write(data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def get_request_line(self, reader: asyncio.StreamReader) -> tuple[str]:
        """
        Read the request line from the client.
        """
        request_line = await reader.readuntil(b"\r\n")
        if not request_line:
            raise ValueError("Request line is empty.")
        request_line = request_line.rstrip(b"\r\n")
        if not request_line:
            raise ValueError("Request line is empty after stripping.")
        request_line = request_line.decode("utf-8").strip()
        if not request_line:
            raise ValueError("Request line is empty after decoding.")
        try:
            method, path, protocol = re.split(r"\s+", request_line)
        except ValueError:
            raise ValueError("Request line is malformed. Unable to split into method, path, and protocol.")
        if not method or not path or not protocol:
            raise ValueError("Request line is malformed. Missing method, path, or protocol.")
        return method.upper(), path, protocol

    async def send_response(self, writer: asyncio.StreamWriter, status_code: int=404, reason: str = "Not found", msg:str="") -> None:
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
            return await self.send_response(writer=writer, status_code=404, reason="Not Found", msg=msg)
        img_src = random.choice(os.listdir("./static/img"))
        newzen = random.choice([self.zen, self.original_zen]).replace("\n", "<br>")
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


async def run_dev_server(protocol: Callable = ProtocolFactory(), host:str=oxi_host, port:int=oxi_port) -> None:
    server = await asyncio.start_server(protocol, host, port, reuse_address=True, reuse_port=True)
    subprocess.run("clear")
    print(f"\n Oxi Server running at {host}:{port}\n")
    async with server:
        try:
            await server.serve_forever()
        except KeyboardInterrupt:
            print("\n Oxi Server stopped by user")
        except Exception as e:
            print(f"\n Oxi Server stopped with error: {e}")
        finally:            
            await server.wait_closed()
            print("\n Oxi Server closed")

async def main():
    protocol = ProtocolFactory(base_dir='')
    await run_dev_server(protocol, host=oxi_host, port=oxi_port)

if __name__ == "__main__":
    asyncio.run(main())
