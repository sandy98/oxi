#!/usr/bin/env python3
#-*- coding: utf_8 -*-

import sqlite3, asyncio, re, inspect, json, os, time, random, contextlib, io
import multiprocessing, threading, sqlite3
import argparse, secrets
from functools import reduce, wraps
from typing import Callable, Any
from http import HTTPStatus
from http.cookies import SimpleCookie
from uuid import uuid4
from urllib.parse import quote_plus, unquote_plus

try:
    from tina import __version__ as tina_version
except:
    from __init__ import __version__ as tina_version

try:
    from tina.utils import SmartDict, FormElement
    from tina.tinaserver import static_app, demo_app, TinaHandler, run_dev_server, to_bytes, strftime_template, tina_port
    from tina.websocket import WebSocket, CONNECTING, CONNECTED, DISCONNECTED, RESPONSE
    from tina.context import current_session
    # from tina.template import load_template, render_template
except Exception as exc:
    try:
        from utils import SmartDict, FormElement
        from tinaserver import static_app, demo_app, TinaHandler, run_dev_server, to_bytes, strftime_template, tina_port
        from websocket import WebSocket, CONNECTING, CONNECTED, DISCONNECTED, RESPONSE
        from context import current_session
        # from template import load_template, render_template
    except Exception as exc:
        # pass
        print(f"Error importing: {exc}")

######################################################################################

# global_flash_queues = SmartDict()

global_session_lock = asyncio.Lock()    

######################################################################################

# What the heck is this?
# def parse_function(func: Callable):
#     parameters = inspect.Signature(func)
#     return parameters

######################################################################################

class Route:
    """
    Represents a path of execution along with the code to be executed.
    """

    def __init__(self, methods=["get"], path="/", func=lambda: b'', 
                 content_type="text/html", content_disposition: str = 'inline'):
        self.methods = methods
        self.path = path
        self.func = func
        self.args = []
        self.kwargs = {}
        self.params_defaults = []
        self.content_type = content_type
        self.content_disposition = content_disposition
        self.func.route = self
        self.pattern, self.types = self.build_pattern()
    
    def __repr__(self):
        return f"""< ROUTE / Methods: {self.methods} - Path: {self.path} - Pattern: {self.pattern_str} - Function: {self.func.__name__} - Type: {self.content_type} >"""

    def match(self, path):
        m = re.match(self.pattern, path)
        if not m:
            if path == self.path:
                self.args = []
                return True
            else:
                return False
        d = m.groupdict()
        type_values = list(self.types.values())
        arg_values = list(d.values())
        if len(type_values) != len(arg_values):
            print(f"type/value mismatch in path {self.path}")
            return False
        for index, t in enumerate(type_values):
            kind = t
            try:
                arg_values[index] = kind(arg_values[index])
            except:
                return False
            # Here we try to coerce, in case we have a string representing a number.
            if kind == str:
                try:
                    arg_values[index] = int(arg_values[index])
                    if self.params_defaults[index] is not None:
                        self.params_defaults[index] = int(self.params_defaults[index])
                    print(f"Converted string '{arg_values[index]}' to int number {arg_values[index]}")
                except:
                    try:
                        arg_values[index] = float(arg_values[index])
                        if self.params_defaults[index] is not None:
                            self.params_defaults[index] = float(self.params_defaults[index])
                        print(f"Converted string '{arg_values[index]}' to float number {arg_values[index]}")
                    except:
                        pass

        self.args = arg_values
        return True

    def build_pattern(self):
        # print(f"Building pattern for path: {self.path}, function: {self.func.__name__}")

        def regex_parser(m):
            # print(f"Beginning regex parser with match object: {m}")
            if not m:
                return '' 
            d = m.groupdict()
            if not d.get("param_name"):
                return ''
            
            params.append(d.get("param_name"))
            param_type = d.get("param_type")
            param_default = d.get("param_default")

            if not param_type:
                params_types.append(type("42"))
            else:
                if not param_type in self.accepted_param_types:
                    raise ValueError(f"Unknown parameter type: {param_type}")
                else:
                    if param_type == 'int':
                        ptype = type(42)
                    elif param_type == 'float':
                        ptype = type(42.)
                    else:
                        ptype = type("42")
                params_types.append(ptype)

            params_defaults.append(param_default)

            # print(f"Returning {self.replace_regex.format(d.get('param_name'))}")
            return self.replace_regex.format(d.get('param_name'))

        params = []
        params_types = []
        params_defaults = []
        working_path = self.path
        m = re.match(".*" + self.param_regex, working_path)

        if not m:
            # print(f"Trying to coerce parameters inspecting function.")
            lparams = inspect.signature(self.func).parameters.items()
            for k, v in lparams:
                working_path += f"/<{str(v)}>"
            # print(f"Working path after inspecting function '{self.func.__name__}' is: {working_path}")
            m = re.match(self.param_regex, working_path)
            # print(f"After inspectiong '{self.func.__name__}' got this match: {m}")

        route_regex = re.sub(self.param_regex, regex_parser, working_path)
        self.pattern_str = "^{}$".format(route_regex)
        self.params_defaults = params_defaults
        return re.compile(self.pattern_str), dict(zip(params, params_types))
    
    @property
    def accepted_param_types(self):
        return ['str', 'int', 'float', 'WebSocket']

    @property
    def param_regex(self):
        # return r"<\s*(?P<param_name>\w+)\s*(:\s*(?P<param_type>\w+))?\s*>"
        return r"<\s*(?P<param_name>\w+)\s*(:\s*(?P<param_type>\w+)(\s*=\s*(?P<param_default>\w+)\s*)?)?\s*>"

    @property
    def replace_regex(self):
        return r'(?P<{}>.+)'

######################################################################################

class TinAException(Exception):
    def __init__(self, status_code: int = 500):
        self.status = HTTPStatus(status_code)
        self.value = self.status.value
        self.phrase = self.status.phrase

    def __repr__(self):
        return f"{self.value} {self.phrase}"

    def __str__(self):
        return self.phrase
    
######################################################################################

class TinApp():
    """
    ASGI App class. Given the server/app scheme, TinaApp is the App, while TinaHandler
    represents the server component.
    Uses route handler functions much like Flask and Bottle style.
    """
    
    def __init__(
            self, 
            routes: list = [], 
            ws_routes: list = [], 
            sse_routes: list = [], 
            nextcall: Callable = None
        ):
        self.routes = routes
        self.ws_routes = ws_routes
        self.sse_routes = sse_routes
        if not nextcall:
            self._next = self.not_found
        else: 
            if TinaHandler.is_wsgi(nextcall):
                self._next = TinaHandler.wsgi2asgi(nextcall)
            else:       
                self._next =  nextcall
        self.create_session_db()

    @property
    def session(self):
        return current_session.get()['session_data']
    
    @property
    def session_id(self):
        return current_session.get()['session_id']
    @session_id.setter
    def session_id(self, new_sid):
        current_session.get()['session_id'] = new_sid

    @property
    def cookies_set(self):
        return current_session.get().get('cookies_set', [])
    @cookies_set.setter
    def cookies_set(self, new_cookies):
        current_session.get()['cookies_set'] = new_cookies

    @property
    def form(self):
        return current_session.get().get('form', {})
    @form.setter
    def form(self, newform):
        current_session.get()['form'] = newform

    @property
    def forms(self):
        return current_session.get().get('forms', {})
    @forms.setter
    def forms(self, newforms):
        current_session.get()['forms'] = newforms

    # @property
    # def flash_queue(self):
    #     queue = global_flash_queues.get(self.session_id,)
    #     if not queue:
    #         queue = asyncio.Queue()
    #         global_flash_queues[self.session_id] = queue
    #     return queue
    
    @property
    def scope(self):
        return current_session.get().get('scope')

    @property
    def receive(self):
        return current_session.get().get('receive', None)

    @property
    def send(self):
        return current_session.get().get('send', None)

    @property
    def req_type(self):
        return current_session.get().get('scope', {}).get('type', 'http')

    @property
    def method(self):
        return current_session.get().get('scope', {}).get('method', 'GET').lower()

    @property
    def path(self):
        return current_session.get().get('scope', {}).get('path', '/')
    @path.setter
    def path(self, new_path):    
        current_session.get()['scope']['path'] = new_path

    def get_session_id(self, scope):
        """ Extracts session ID from cookies """
        headers = dict(scope["headers"])
        cookies = headers.get(b"cookie", b"").decode()
        cookies = {k.strip(): v.strip() for k, v in (c.split("=") for c in cookies.split(";") if "=" in c)}
        session_id = cookies.get("session_id")  # Generate new session if missing
        if not session_id:
            print("Generating new session ID")
            session_id = secrets.token_hex(16)
        else:
            pass
            # print(f"Session ID: {session_id}")
        return session_id
    
    def create_session_db(self):
            filename = f"{self.session_directory}{os.path.sep}sessions.sqlite"
            try:
                # with open(filename, 'w') as sess_file:
                #     json.dump(session, sess_file)
                conn = sqlite3.connect(filename)
                create_session_table = f"""
    CREATE TABLE IF NOT EXISTS `sessions` (
    `sid` TEXT NOT NULL primary key,
    `session` TEXT NOT NULL
    );
    """
                conn.execute(create_session_table)
                conn.commit()
                
            except Exception as exc:
                print(f"Couldn't save session file because of {exc}")

    async def save_session(self) -> None:
        initial_session_data = current_session.get().get('initial_session_data')
        # if self.session == initial_session_data:
        #     pass
        #print(f"Saving session {self.session_id}")
        filename = f"{self.session_directory}{os.path.sep}sessions.sqlite"
        dumped_session = json.dumps(self.session, ensure_ascii=False)
        def save_sess_data():
            try:
                conn = sqlite3.connect(filename)
                cur = conn.execute('select count(*) from sessions where sid = ?;', [self.session_id])
                if not cur.fetchone()[0]:
                    print(f"Inserting new session {self.session_id}")
                    conn.execute('insert into sessions (sid, session) values (?, ?);', [self.session_id, dumped_session])
                else:
            #       print(f"Updating session {self.session_id}")
                    conn.execute('update sessions set session = ? where sid = ?;', [dumped_session, self.session_id])
                conn.commit()
            except Exception as exc:
                print(f"{exc.__class__.__name__}: Couldn't save session because of {exc}")
        async with global_session_lock:
            coro = asyncio.to_thread(save_sess_data)
            await coro

    async def get_session_data(self, session_id) -> SmartDict:
        filename = f"{self.session_directory}{os.path.sep}sessions.sqlite"
        session =SmartDict(user=None, csrf_token=TinaHandler.generate_csrf_token())
        def retrieve_func():
            try:
                conn = sqlite3.connect(filename)
                cur = conn.execute('select count(*) from sessions where sid = ?;', [session_id])
                if not cur.fetchone()[0]:
                    conn.execute('insert into sessions (sid, session) values (?, ?);', [session_id, json.dumps(session)])
                    conn.commit()
                    return session
                else:
                    cur = conn.execute('select session from sessions where sid = ?;', [session_id])
                    oldSession = SmartDict(json.loads(cur.fetchone()[0]))
                    return oldSession
            except Exception as exc:
                print(f"Couldn't load session {session_id} because of {exc}")
                return session

        async with global_session_lock:
            coro = asyncio.to_thread(retrieve_func)
            return await coro

    async def store_session_data(self, session_id: str, session_data: SmartDict) -> None:
        filename = f"{self.session_directory}{os.path.sep}sessions.sqlite"
        session = SmartDict(user=None, csrf_token=TinaHandler.generate_csrf_token())
        def store_the_data():
            try:
                conn = sqlite3.connect(filename)
                cur = conn.execute('select count(*) from sessions where sid = ?;', [session_id])
                if not cur.fetchone()[0]:
                    conn.execute('insert into sessions (sid, session) values (?, ?);', [session_id, json.dumps(session_data)])
                    conn.commit()
                else:
                    conn.execute('update sessions set session = ? where sid = ?;', [json.dumps(session_data), session_id])
                    conn.commit()
            except Exception as exc:
                print(f"Couldn't save session {session_id} because of {exc}")
        async with global_session_lock:
            coro = asyncio.to_thread(store_the_data)
            await coro


    async def set_session_value(self, key: str, value: Any) -> None:
        self.session[key] = value
        await self.save_session()

    async def __call__(self, scope: dict, receive: Callable, send: Callable)-> None:
        session_id = self.get_session_id(scope)
        session_data = await self.get_session_data(session_id)
        session_token = current_session.set(SmartDict(session_id=session_id, 
                                                      session_data=session_data, 
                                                      initial_session_data=session_data, 
                                                      receive=receive, send=send, ))
        # if session_id not in global_flash_queues:
        #     global_flash_queues[session_id] = asyncio.Queue()
        self.set_cookie('session_id', session_id, max_age=60 * 60)
        current_session.get()['scope'] = scope
        current_session.get()['receive'] = receive
        current_session.get()['send'] = send
 
        if scope["type"].lower() == "lifespan":
           message = await receive()
           if message["type"].lower() == "lifespan.startup":
                print("Starting up ASGI application...")
                await send({"type": "lifespan.startup.complete"})
                await self.save_session()
                return current_session.reset(session_token)
           elif message["type"].lower() == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                await self.save_session()
                return current_session.reset(session_token)
           else:
                raise ValueError(f"Unexpected message: {message}")

        if self.scope.get("path").endswith("/") and len(self.scope.get("path")) > 1:
            self.scope['path'] = self.scope.get('path')[:-1]

        if not self.session.get('csrf_token'):
            await self.set_session_value(self.session, 'csrf_token', TinaHandler.generate_csrf_token())

        response_body = b''
        target_routes = []
        if self.req_type == 'websocket':
            for routedict in self.ws_routes:
                if routedict.path.startswith(self.path):
                    ws = WebSocket(scope, receive, send)
                    await routedict.func(ws)
                    await self.save_session()
                    current_session.reset(session_token)
                    return
        elif self.path in map(lambda entry: entry.get('path'), self.sse_routes):
            target_routes = self.sse_routes
        elif self.method == 'head':
            target_routes = self.head_routes
        elif self.method == 'get':
            target_routes = self.get_routes
        elif self.method == 'post':
            target_routes = self.post_routes
        elif self.method == 'put':
            target_routes = self.put_routes
        elif self.method == 'patch':
            target_routes = self.patch_routes
        elif self.method == 'delete':
            target_routes = self.delete_routes
        else:
            await self.next(self.scope, receive, send)
            await self.save_session()
            return current_session.reset(session_token)
        
        if self.path == '/demo':
            await demo_app(self.scope, receive, send)
            await self.save_session()
            return current_session.reset(session_token)
        
        curr_route = None
        if target_routes == self.sse_routes:
            for routedict in self.sse_routes:
                if routedict.path.startswith(self.path):
                    response_body = await routedict.func() 
        else:
            for route in target_routes:
                if route.match(self.path):
                    if self.method not in ['get', 'head', 'options', 'delete']:
                        msg = await receive()
                        body = msg.get('body')
                        if b'form-data' in body:
                            self.forms = await TinaHandler.form_list(scope, body)
                            self.form = None
                            for f in self.forms:
                                if 'filename' in f:
                                    self.form = f
                                    break
                            if not self.form:
                                self.form = self.forms[0]
                        else:
                            self.form = await TinaHandler.form(scope, body)
                            self.forms = [self.form]
                    else:
                        self.form = await TinaHandler.form(scope, b'')
                        self.forms = [self.form]
                    try:
                        if inspect.iscoroutinefunction(route.func):
                            response_body = await route.func(*route.args, **route.kwargs)
                            if not inspect.isasyncgen(response_body):
                                response_body = to_bytes(response_body)
                        else: 
                            # response_body = to_bytes(route.func(*route.args, **route.kwargs))
                            response_body = to_bytes(await asyncio.to_thread(route.func,*route.args, **route.kwargs))
                    except TinAException as exc:
                        await self.error(code=exc.value, phrase=exc.phrase, scope=scope, _= receive, send=send)
                        await self.save_session()
                        return current_session.reset(session_token)
                    except Exception as exc:
                        print(f"Exception occurred: {exc} while handling path: {self.path}")
                        await self.error(code=500, phrase=str(exc), scope=scope, _= receive, send=send)
                        await self.save_session()
                        return current_session.reset(session_token)
                    curr_route = route
                    break
        if inspect.isasyncgen(response_body):
            try:
                response_headers = [
                    (b'content-type', b'text/event-stream'), 
                    (b'cache-control', b'no-cache'), 
                    (b'x-accel-buffering', b'no')
                    ]
                startdict = SmartDict(type='http.response.start', status=200, headers=response_headers)
                await send(startdict)
                async for item in response_body:
                    try:
                        if len(item) == 0:
                            bodydict = SmartDict(type='http.response.body', body=b'', more_body=False)
                            await send(bodydict)
                            break
                        bodydict = SmartDict(type='http.response.body', body=to_bytes(item), more_body=True)
                        await send(bodydict)
                    except:
                        break
            except Exception as exc:
                print(f"Exception occurred while sending asyncgen content to client on route '{scope.get('path')}': {exc}")
                task = asyncio.create_task(response_body.__anext__())
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            finally:
                await response_body.aclose()
                print("Async generator closed.")
                # await self.save_session()
                # current_session.reset(session_token)

        elif len(response_body):
            total_len = 0
            if not isinstance(response_body, (tuple, list)):
                response_body = [response_body]
            total_len = sum(map(len, response_body))
            response_headers = [(b'content-type', curr_route.content_type.encode('utf-8    ')), (b'content-length', str(total_len).encode('utf-8'))]
            if hasattr(curr_route, 'content_disposition') and curr_route.content_disposition:
                response_headers = [*response_headers, (b'content-disposition', to_bytes(curr_route.content_disposition))]
            if len(self.cookies_set):
                response_headers += self.cookies_set
                self.cookies_set = []
            try:
                startdict = SmartDict(type='http.response.start', status=200, headers=response_headers)
                await send(startdict)
            except:
                pass
            for item in iter(response_body):
                try:
                    bodydict = SmartDict(type='http.response.body', body=item, more_body=True)
                    await send(bodydict)
                except:
                    pass
            try:
                bodydict = SmartDict(type='http.response.body', body=b'', more_body=False)
                await send(bodydict)
            except:
                pass
            print(f"\n(PID {os.getpid()}) {self.method.upper()} {self.path} request from {scope.get('client',['unknown', 'unknown'])[0]} {time.strftime('%Y-%m-%d %H:%M:%S')} - {200}")
            await self.save_session()
            current_session.reset(session_token)
        else:
            await self.next(self.scope, receive, send)
            await self.save_session()
            current_session.reset(session_token)

    async def send_static(self):
        return await static_app(self.scope, self.receive, self.send, True)
    
    @classmethod
    def scaffold(cls, filename: str=None, menu_items: list[tuple[str, str]]=[]):
        h1style = "'text-align: center; margin-top: 0.5em;'"
        lines = [
            "#!/usr/bin/env python3",
            "#-*- coding: utf_8 -*-",
            "",
            "import asyncio",
            "from tinaserver import run_dev_server, static_app, tina_port",
            "from tinapp import TinApp",
            "from template import NavBar, MenuItem, Head, Body, HTMLApp, render_template, load_template",
            "",
            'itemHome = MenuItem("Home", "/")',
            'itemAbout = MenuItem("About", "/about")',
            'navBar = NavBar(head="Skeleton TinA App", items=[itemHome, itemAbout])',

        ]

        handlers_lines = []
        if len(menu_items):
            menu_items.reverse()
            for index, menu_item in enumerate(menu_items):
                newitem = f'item{index}'
                newline = f'{newitem} = MenuItem("{menu_item[0].title()}", "{menu_item[1]}")'
                lines.append(newline)
                newline = f'navBar.items.insert(1, {newitem})'
                lines.append(newline)
                handlers_lines.append(f'@skel_app.get("{menu_item[1]}")')
                handlers_lines.append(f'def func_{newitem}():')
                handlers_lines.append(f'    info = "<h1 style={h1style}>{menu_item[0].title()} page</h1>"')
                handlers_lines.append('    return render_template(str(htmlApp), contents=info)')
                handlers_lines.append('')

        lines.append('htmlApp = HTMLApp(head=Head(title="Skeleton TinA App"), body=Body(navbar=navBar))')
        lines.append('')
        lines.append('skel_app = TinApp()')
        lines.append('skel_app.set_next(static_app)')
        lines.append('')

        lines.append('@skel_app.get("/")')
        lines.append('def home():')
        lines.append(f'    home_info = "<h1 style={h1style}>Home page</h1>"')
        lines.append('    return render_template(str(htmlApp), contents=home_info)')
        lines.append('')
        lines.append('@skel_app.get("/about")')
        lines.append('def about():')
        lines.append(f'    about_info = "<h1 style={h1style}>About page</h1>"')
        lines.append('    return render_template(str(htmlApp), contents=about_info)')
        lines.append('')

        for l in handlers_lines:
            lines.append(l)

        lines.append('def main():')
        lines.append('    try:')
        lines.append('        asyncio.run(run_dev_server(app=skel_app, host="0.0.0.0", port=tina_port))')
        lines.append('    except KeyboardInterrupt:')
        lines.append('        print()')
        lines.append('        print("Server closing. Bye for now...")')
        lines.append('')
        lines.append('if __name__ == "__main__":')
        lines.append('    main()')
        lines.append('')
        lines.append('#Skeleton App End')



        fp = open(filename, 'w') if filename else os.sys.stdout
        text = '\n'.join(lines)
        fp.write(text)
        if filename:
            fp.close()
            os.chmod(filename, 0o755)
        else:
            fp.flush()

        return text
    
#################################################################################################################################
            
    def set_next(self, next_app):
        if TinaHandler.is_wsgi(next_app):
            self._next = TinaHandler.wsgi2asgi(next_app)
        else:
            self._next = next_app

    async def next(self, scope: dict, receive: Callable, send: Callable) -> None:
        return await self._next(scope, receive, send)
    
    async def error(self, code: int = 404, phrase: str = 'Not found', 
                    scope: SmartDict= None, _: Any = None, send: Callable= None):
        # body = f'<p><span style="color: red;">{code}</span>&nbsp;<span>{phrase}</span></p>'
        body = TinaHandler.get_error_template().format(code, code, self.scope.get('path'), phrase, tina_version)
        headers = [(b'content-type', b'text/html; charset=utf-8'), (b'content-length', str(len(body)).encode('utf-8'))]
        startdict = {
            'type': 'http.response.start',
            'status': code,
            'headers': headers
        }
        bodydict = {
            'type': 'http.response.body',
            'body': body.encode('utf-8    '),
            'more_body': False
        }
        try:
            await self.send(startdict)
        except Exception as exc:
            print(f"Ha ocurrido una excepción al enviar las cabeceras de un error previo: {exc}")
        try:    
            return await self.send(bodydict)
        except Exception as exc:
            print(f"Ha ocurrido una excepción al enviar el contenido  de un error previo: {exc}")

    async def not_found(self, scope: SmartDict, _: Any = None, send: Callable = None):
        return await self.error(code=404, phrase=f'{scope.get("path")} not found.', scope=scope, send=send)

    async def internal_error(self, scope: SmartDict, _: Any = None, send: Callable = None):
        return await self.error(code=500, phrase='Internal server error.', scope=scope, send=send)

    async def redirect(self, where):
        response_headers = [(b'location', to_bytes(where))]
        if len(self.cookies_set):
            response_headers += self.cookies_set
            self.cookies_set = []
        start_dict = SmartDict(type='http.response.start', status=303, headers=response_headers)
        body_dict = SmartDict(type='http.response.body', body=b'', more_body=False)
        await self.send(start_dict)
        await self.send(body_dict)

    async def nocontent(self):
        response_headers = [(b'content-length', b'0')]
        if len(self.cookies_set):
            response_headers += self.cookies_set
            self.cookies_set = []
        start_dict = SmartDict(type='http.response.start', status=204, headers=response_headers)
        body_dict = SmartDict(type='http.response.body', body=b'', more_body=False)
        await self.send(start_dict)
        await self.send(body_dict)

    async def reload(self, what):
        response_headers = [(b'location', to_bytes(what))]
        if len(self.cookies_set):
            response_headers += self.cookies_set
            self.cookies_set = []
        start_dict = SmartDict(type='http.response.start', status=303, headers=response_headers)
        body_dict = SmartDict(type='http.response.body', body=b'', more_body=False)
        await self.send(start_dict)
        await self.send(body_dict)

    def add_route(self, route: Route, is_ws: bool = False) -> None:
        route.app = self
        route.func.app = self
        if is_ws:
            self.ws_routes.append(route)
        else:    
            self.routes.append(route)
        return route

    def route(self, path, methods=['GET'], content_type="text/html; charset=utf-8", content_disposition="inline"):
        def route_adder(func):
            self.add_route(Route(methods=methods, path=path, func=func, 
                                 content_type=content_type, content_disposition=content_disposition))
            return func
        return route_adder

    def websocket(self, path):
        def route_adder(func):
            self.ws_routes.append(SmartDict(path=path, func=func)) 
            return func
        return route_adder
   
    def sse(self, path):
        def route_adder(asyncgen_func):
            @wraps(asyncgen_func)
            async def asyncgen_wrapper(*args, **kwargs):
                return asyncgen_func(*args, **kwargs)
            self.sse_routes.append(SmartDict(path=path, func=asyncgen_wrapper)) 
            return asyncgen_wrapper
        return route_adder
         
    def head(self, path, methods=["HEAD"], content_type="text/plain; charset=utf-8", content_disposition="inline"):
        return self.route(path, methods=methods, content_type=content_type, content_disposition=content_disposition)
        
    def get(self, path, methods=["GET"], content_type="text/html; charset=utf-8", content_disposition="inline"):
        return self.route(path, methods=methods, content_type=content_type, content_disposition=content_disposition)
        
    def post(self, path, methods=["POST"], content_type="text/html; charset=utf-8", content_disposition="inline"):
        return self.route(path, methods=methods, content_type=content_type, content_disposition=content_disposition)
        
    def put(self, path, methods=["PUT"], content_type="text/html; charset=utf-8", content_disposition="inline"):
        return self.route(path, methods=methods, content_type=content_type, content_disposition=content_disposition)
        
    def patch(self, path, methods=["PATCH"], content_type="text/html; charset=utf-8", content_disposition="inline"):
        return self.route(path, methods=methods, content_type=content_type, content_disposition=content_disposition)
        
    def delete(self, path, methods=["DELETE"], content_type="text/html; charset=utf-8", content_disposition="inline"):
        return self.route(path, methods=methods, content_type=content_type, content_disposition=content_disposition)
        
    def method_routes(self, method):
        return [r for r in self.routes if method.upper() in r.methods]

    def login_required(self, redirect_to: str= '/', failure_msg: str='Login required.', timeout:int=3):
        def handle_login(func):
            @wraps(func)
            async def login_wrapper(*args, **kw):
                if 'user' in self.session and self.session.get('user') and 'fullname' in self.session.user and ('username' in self.session.user or 'email' in self.session.user):
                    if inspect.iscoroutinefunction(func):
                        return await func(*args, **kw)
                    else:
                        return func(*args, *kw)
                else:
                    await self.set_flash(level='warning', msg=failure_msg, timeout=timeout)
                    await self.redirect(f"{redirect_to}")
                    return b''
            return login_wrapper
        return handle_login
    
    def get_cookies(self) -> list[tuple[bytes, bytes]]:
        if not self.scope:
            return []
        cookies_header = TinaHandler.get_request_header(self.scope, 'cookie')
        if not cookies_header:
            return []
        cookies_header = cookies_header.decode('utf-8')
        sc = SimpleCookie(cookies_header)
        if not len(sc):
            return []
        return list(map(lambda t: (to_bytes(unquote_plus(t[0])), to_bytes(unquote_plus(t[1].value))), sc.items()))
    
    def get_cookie(self, key: str):
        cookies = self.get_cookies()
        for k, v in cookies:
            if k == key.encode():
                return v.decode()
        return None
    
    def set_cookie(self, key: str, value: str, max_age: int= None):
        header_key = b"set-cookie"
        header_val = f"{quote_plus(key)}={quote_plus(value)};{'max-age=' if max_age else''}{max_age if max_age else ''}{';' if max_age else ''}".encode('utf-8    ')
        cookies_set = self.cookies_set
        cookies_set.append((header_key, header_val))
        current_session.get()['cookies_set'] = cookies_set

    def del_cookie(self, key: str):
        self.set_cookie(key, '', 0)

    async def get_flash(self) -> SmartDict:
        if 'flash' in self.session:
            flash = self.session['flash']
            # del self.session['flash']
            await self.del_session_value('flash')
            await self.save_session()
            return flash
        else:
            previous_session_data = await self.get_session_data(self.session_id)
            if 'flash' in previous_session_data:
                flash = previous_session_data.get('flash')
                if flash:
                    # del previous_session_data['flash']
                    # await self.store_session_data(self.session_id, previous_session_data)
                    # return flash    
                    self.session.update(previous_session_data)
                    return await self.get_flash()
        return None

        # if not global_flash_queues.get(self.session_id):
        #     global_flash_queues[self.session_id] = asyncio.Queue()
        # try:
        #     return await asyncio.wait_for(global_flash_queues[self.session_id].get(), timeout=1)
        # except asyncio.TimeoutError:
        #     return SmartDict(level='info', msg='OK', timeout=0)
        
    async def set_flash(self, level: str, msg: str, timeout: int = 5, time2sleep: int = 1): 
        if level not in ['info', 'warning', 'error']:
            level = 'info'

        # async def borra_flash():
        #     await asyncio.sleep(time2sleep)
        #     # print("Ya dormí {time2sleep} seconds. Now to kill Flash.... :-) ")
        #     del session['flash']
        #     await self.save_session(session)

        # def cb(t):
        #     print("Flash borrado de la sesión.")
        newflash = SmartDict({'level': level, 'msg': msg, 'timeout': timeout})
        await self.set_session_value('flash', newflash)
        # await self.flash_queue.put(newflash.copy())

        # self.session['flash'] = {'level': level, 'msg': msg, 'timeout': timeout}

        # if not self.session_id in global_flash_queues:
        #     global_flash_queues[self.session_id] = asyncio.Queue()
        # queue = self.flash_queue
        # queue = global_flash_queues[self.session_id]
        # await queue.put(SmartDict(level=level, msg=msg, timeout=timeout, time2sleep=time2sleep))
        # task = asyncio.create_task(borra_flash())
        # task.add_done_callback(cb)

        # Ver si no hay que lanzar un thread que borre el flash

    async def del_session_value(self, key: str) -> None:
        if key in self.session:
            del self.session[key]
            await self.save_session()

    def mount(self, app: Callable, mounted_path: str, src_path: str = "/") -> None:
        @self.route(mounted_path)
        async def mounted_func():
            new_scope = self.scope.copy()
            new_scope['path'] = src_path
            new_scope['wsgi_environ']['PATH_INFO'] = src_path
            new_app = app
            if TinaHandler.is_wsgi(app):
                new_app = await TinaHandler.wsgi2asgi(new_scope, self.receive, self.send, app)
            await new_app(new_scope, self.receive, self.send)
            return b''
    
    @property
    def session_directory(self):
        directory = os.path.abspath(TinaHandler.config.get('sessions-dir', 'sessions'))
        if not directory:
            return None
        if not os.path.exists(directory):
            os.mkdir(directory)
        return directory
    
    @property
    def head_routes(self):
        return self.method_routes('head')

    @property
    def get_routes(self):
        return self.method_routes('get')

    @property
    def post_routes(self):
        return self.method_routes('post')

    @property
    def put_routes(self):
        return self.method_routes('put')

    @property
    def delete_routes(self):
        return self.method_routes('delete')

    @property
    def patch_routes(self):
        return self.method_routes('patch')

    @property
    def functions(self):
        return list(map(lambda r: r.func.__name__, self.routes))

    @property
    def patterns(self):
        return list(map(lambda r: r.pattern_str, self.routes))

    @property
    def paths(self):
        return list(map(lambda r: r.path, self.routes))

    @property
    def routes_info(self):
        return list(zip(self.functions, self.paths, self.patterns))

######################################################################################

def main():
    parser = argparse.ArgumentParser(description='Command line arguments for TinApp', prog='tinapp')
    parser.add_argument('-b', '--build_app', action="store_true", help="Creates a new skeleton app and saves it to --outputfile (defaults to 'app.py')")
    parser.add_argument('-o', '--outputfile', type=str, default='app.py', help="Name of the python file for the new scaffold app. Defaults to 'app.py'")
    parser.add_argument('-p', '--port', type=int, default=tina_port)
    parser.add_argument('-a', '--host', type=str, default='0.0.0.0')
    parser.add_argument('-V', '--version', action='version', version=f"{parser.prog} v {tina_version}", help=f"Shows {parser.prog} version and exits.")
    
    args = parser.parse_args()
    
    if args.build_app:
        TinApp.scaffold(args.outputfile)
        print(f"\nSkeleton app successfully built and saved to: '{args.outputfile}'")
        return
    
    try:
        import uvloop
        print(f"UVloop imported successfully.")
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print(f"Event loop policy successfully set to UVloop.\n")
    except:
        print("UVloop not found\n")



    # os.chdir(os.path.split(os.path.abspath(__file__))[0])
    os.system("clear")
    App = example_app
    try:
        # asyncio.run(run_server(App, multithread=True, num_threads=4))
        asyncio.run(run_dev_server(App, host=args.host, port=args.port))
    except KeyboardInterrupt:
        print()
        print("Tina server shutting down.\nBye for now...")
        os.sys.exit(0)
    except Exception as exc:
        print(f"ERROR: {exc}\Exiting...")
        os.sys.exit(-1)

######################################################################################

example_app = None

if __name__ == '__main__':
    from test_app import test_app
    example_app = test_app()
    main()

######################################################################################

