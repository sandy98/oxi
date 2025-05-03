# -*- coding: utf-8 -*-

from typing import Callable

try:
    from . import  __version__ as oxi_version, __oxi_port__ as oxi_port, __oxi_host__ as oxi_host
    from .utils import is_windows, is_linux, is_mac, to_bytes
    from .config import Config
except ImportError:
    from activate_this import oxi_env
    if not oxi_env:
        raise ImportError("Oxi environment not activated. Please activate the virtual environment.")
    from oxi import  __version__ as oxi_version, __oxi_port__ as oxi_port, __oxi_host__ as oxi_host
    from oxi.utils import is_linux, is_windows, is_mac
    from oxi.config import Config

oxi_version

async def static_app(scope: dict, receive: Callable, send: Callable, absolute_path= False)-> None:

    remote_host = scope.get('remote-host')
    # remote_ip = scope.get('x-real-ip')
    remote_ip = scope.get('client', ['unknown','unknown'])[0]
    method = scope.get('method').upper()
    pth = scope.get('path')
    if pth.endswith("/") and len(pth) > 1:
        pth = pth[:-1]

    async def send_error(code, resource = None):
        statusobj = HTTPStatus(code)
        template = TinaHandler.get_error_template()
        resource = '' if resource is None else str(resource)
        body = template.format(statusobj.value, statusobj.value, resource, statusobj.phrase, tina_version)
        body_len = len(body)
        print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {statusobj.value}")
        
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
                request_body  = scope.get('request_body') + b'\r\n'
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
        print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")

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

        print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")

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

        print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")

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
                        print(f"Finished reading {scope.get('path', '---')}")
                    await send({
                        "type": "http.response.body",
                        "body": part, 
                        "more_body": True
                    })
                except BlockingIOError as e:
                    if e.errno == errno.EAGAIN:
                        # No data available *right now*, try again later
                        # print("No data ready yet, try again")
                        asyncio.sleep(0)
                        continue
                    else:
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
        print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 200")
        
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
            environ['REQUEST_METHOD'] = scope.get("method").upper()
            environ['CONTENT_LENGTH'] =  str(len(request_body))
            environ['SERVER_NAME'] = scope.get('server_name')
            environ['SERVER_PORT'] = scope.get('local_port')
            environ['REMOTE_HOST'] = scope.get('remote-host')
            environ['REMOTE_PORT'] = scope.get('remote-port')
            environ['QUERY_STRING'] = scope.get('query_string').decode('utf-8')
            environ['CGI_PATH'] = scope.get('path')
            environ['SCRIPT'] = os.path.split(scope.get('path'))[1]
            environ['X-REAL-IP'] = scope.get('x-real-ip')

            for [k, v] in scope.get("headers"):
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
            print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {code.decode('utf-8')}")
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
                    print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
                    return await send_error(403, os.path.split(cgipath)[1])
            else:
                print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
                return await send_error(403,  os.path.split(cgipath)[1])
        else:
            print(f"\n(PID {os.getpid()}) {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 403")
            return await send_error(403,  os.path.split(cgipath)[1])

    body = ""     
    static_dir = TinaHandler.config.get('static-dir', 'static')
    if not static_dir or (not os.path.exists(static_dir)) or absolute_path:
        # static_dir = os.path.split(os.getcwd())[1]
        static_dir = "."
    # print(f"static directory is: {static_dir}")
    cgi_dir = TinaHandler.config.get('cgi-dir')
    # print(f"CGI directory is: {cgi_dir}")
    pth = (scope and scope.get('path')) or ''
    # print(f"Requested path is: {pth}")
    fullpath = ""
    is_cgi = False 



    if TinaHandler.config.get('redirects') and pth[1:] in TinaHandler.config.get('redirects').keys():
        d = TinaHandler.config.get('redirects')
        where = d.get(pth[1:])
        print(f"(PID {os.getpid()}) \nRedirect {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - 302")
        return await send_redirection(where)

#    if pth[1:] in TinaHandler.config.get('proxy_pass').keys():
    for key in TinaHandler.config.get('proxy_pass').keys():
        if pth[1:].startswith(key):
            d = TinaHandler.config.get('proxy_pass')
            # where = d.get(pth[1:])
            where = d.get(key)
            retcode = await send_proxy_pass(key, where)
            print(f"\n(PID {os.getpid()}) Proxy pass {method} {pth} request from {remote_ip}({remote_host}) {time.strftime('%Y-%m-%d %H:%M:%S')} - {retcode}")
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

    m = re.match(f".*{cgi_dir}.*", pth)
    # print(f"CGI string in position in path is: {m}")
    if m:
        is_cgi = True
        fullpath = f"{os.path.abspath('.')}{pth}"
    else:
        fullpath = f"{os.path.abspath(static_dir)}{pth}"
    # print(f"Full path is: '{fullpath}' and it is {'' if is_cgi else 'not '}CGI content.")


    if pth == '/':
        candidates = ['index.html', 'index.htm']
        for candidate in candidates:
            if await asyncio.to_thread(os.path.exists, f"{fullpath}{candidate}"):
                fullpath += candidate
                # print(f"Real fullpath: {fullpath}")
                break

    requires_body: bool = scope and scope.get('method').lower() not in ['get', 'head', 'options']
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


class OxiApp: ...




