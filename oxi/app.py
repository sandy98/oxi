import sys
from typing import Callable, Any
from pathlib import Path
from inspect import iscoroutinefunction

filepath = Path(__file__)
# print(str(filepath))
parentpath = filepath.parent
# print(str(parentpath))
grandparentpath = parentpath.parent
# print(str(grandparentpath))
sys.path.insert(0, str(parentpath))
sys.path.insert(0, str(grandparentpath))

# from tina.tinapp import TinApp

try:
    # When imported as a package (e.g., `import oxi.app`)
    from .__about__ import __config__ as CONFIG
    from .__about__ import  __version__
    from .tina.tinapp import TinApp
    from .utils import to_bytes
    from .server import get_styled_date
except ImportError:
    # When run as a script or dynamically loaded
    from __about__ import __config__ as CONFIG
    from __about__ import  __version__
    from tina.tinapp import TinApp
    from utils import to_bytes
    from server import get_styled_date

class OxiApp(TinApp):
    """
    Main App class of Oxi framework
    """
    def __init__(self, name:str|None=None,  *args , **kw):
        super(OxiApp, self).__init__(*args, **kw)
        self.config = CONFIG
        self.version = __version__
        self.name = name or self.__class__.__name__
        self.private_state:dict | None = {}
        if 'state' in kw:
            self.private_state = kw['state']
        self._startup_funcs = []
        self._shutdown_funcs = []

    async def __call__(self, scope, receive, send):
        """
        ASGI callable interface for the OxiApp class.
        This method handles incoming ASGI requests and manages the application lifecycle events.
        It processes 'lifespan' messages for startup and shutdown events, and delegates other requests
        to the parent class's __call__ method.
        """
        if scope['type'] == 'lifespan':
            # print("Received 'lifespan' message")
            self.private_state = scope.get('state')
            while True:
                message = await receive()
                if message.get('type', '') == 'lifespan.startup':
                    try:
                        # 🚀 Run user-defined startup hooks
                        for func in self._startup_funcs:
                            if iscoroutinefunction(func):
                                await func()
                            else:
                                func()
                        await send({'type': 'lifespan.startup.complete'})
                    except Exception as exc:
                        # If startup fails, we MUST tell the server
                        import traceback
                        traceback.print_exc()
                        await send({
                            'type': 'lifespan.startup.failed',
                            'message': str(exc)
                        })
                        return # Exit the lifespan loop entirely                
                elif message.get('type', '') == 'lifespan.shutdown':
                    try:
                        for func in self._shutdown_funcs:
                            if iscoroutinefunction(func):
                                await func()
                            else:
                                func()
                        await send({'type': 'lifespan.shutdown.complete'})
                        return
                    except Exception as exc:
                        # If shutdown fails, we MUST tell the server
                        import traceback
                        traceback.print_exc()
                        await send({
                            'type': 'lifespan.shutdown.failed',
                            'message': str(exc)
                        })
                        return # Exit the lifespan loop entirely                
        else: 
            await super(OxiApp, self).__call__(scope, receive, send)

    async def error(self, code, phrase, scope, _, send, msg:str=""):
        """
        Error handler for the OxiApp class. This method generates an HTML error page and sends it as a response.
        """
        html_error_payload = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>{code} {phrase}</title>
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
                    <h1>{code} {phrase}</h1>
                    <p>{msg}</p>
                    <div class="details">
                        <b>Client IP:</b> {to_bytes(scope.get('client', ['localhost', 0])[0]).decode('latin-1')}<br>
                        <b>Request:</b> {scope.get('method', 'GET')} {scope.get('path', '/')} {scope.get('protocol', 'HTTP/1.1')}<br>
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
                'status': code,
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

    def on_startup(self, func):
        """Adds startup logic contained in 'func'"""
        self._startup_funcs.append(func)
        return func

    def on_shutdown(self, func):
        """Adds shutdown logic contained in 'func'"""
        self._shutdown_funcs.append(func)
        return func

    def mount(self, app: Callable, mounted_path: str, src_path: str = "/") -> None:
        """
        Adds an external ASGI app to the OxiApp instance at the specified mounted_path, 
        allowing composition of multiple ASGI applications within a single OxiApp instance.
        """
        super(OxiApp, self).mount(app, mounted_path, src_path)
        if src_path == "/":
            # local_paths = list(map(lambda r: r.path, self.routes))
            local_paths = [r.path for r in self.routes]
            foreign_paths = []
            if hasattr(app, "routes"):
                # Monta rutas secundarias para instancias de OxiApp
                foreign_routes = getattr(app, "routes", [])
                foreign_paths = list(filter(lambda r: r != src_path and r not in local_paths, map(lambda x: f'/{getattr(x, "path").lstrip("/")}', foreign_routes)))
            elif hasattr(app, "url_map"):
                # Monta rutas secundarias para instancias de Flask
                flask_app: Any = app
                try:
                    f_paths = [f'/{getattr(rule, "endpoint").lstrip("/")}' for rule in flask_app.url_map.iter_rules() if getattr(rule, "endpoint").lstrip("/") not in ["flask_root", "static"]]
                    foreign_paths = list(filter(lambda r: r != src_path and r not in local_paths, f_paths))
                except:
                    pass
            for path in foreign_paths:
                super(OxiApp, self).mount(app, mounted_path=path.replace('{','<').replace('}', '>'), src_path=path)

    def links_list(self):
        return "".join([f'<p><a href="{link}">{link}</a></p>' for link in (r.path for r in self.routes)])
    

    
def run_demo():
    """
    Runs the demo application using the OxiApp framework.
    This function clears the terminal, starts the demo application, and handles keyboard interrupts gracefully."""
    import subprocess
    subprocess.run("clear")
    try:
        # run(minidemoapp, "0.0.0.0", 8086)
        subprocess.run(["python3", "server.py", "apps.demo:app"])
    except KeyboardInterrupt:
        print("\nDemo App quitting...")
        sys.exit(0)

if __name__ == '__main__':
    run_demo()