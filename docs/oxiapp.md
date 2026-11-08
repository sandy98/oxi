# OxiApp Framework

`OxiApp` is a fast, simple, and lightweight ASGI micro-framework for Python. It is built on top of **TinA** (Tiny Asynchronous) and draws heavy inspiration from Bottle.

It is designed to give you the elegance of synchronous micro-frameworks (like Bottle or Flask) while fully embracing the modern `async`/`await` capabilities of ASGI.

Creating an App
---------------

Creating an app is as simple as instantiating the `OxiApp` class. You can optionally pass a name to identify your application in logs.

```python

from oxi.app import OxiApp

app = OxiApp("My Awesome App")

```

Routing
-------

OxiApp uses decorators to bind functions to URL paths. It supports all standard HTTP methods.
```python
@app.get("/")
async def index():
    return "Hello, World!"

@app.post("/users")
async def create_user():
    return {"status": "User created"}
```


