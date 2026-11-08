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

@app.post("/users", content_type="application/x-json")
async def create_user():
    try:
        user = app.form.get("user", "")
        pwd = app.form.get("pwd", "")
        if (len(usr) and len(pwd)):
            return {"status": "User created"}
        else:
            return await app.error(403, "Bad user and/or password")
    except:
        return await app.error(400, "Malformed request")
```

Dynamic URLs & Path Parameters
------------------------------

You can define dynamic segments in your routes using angle brackets `<>`. OxiApp will automatically extract them and pass them to your function as arguments.

```python
@app.get("/hello/<name:str>")
@app.get("/hello")
async def hello(name: str = "Stranger"):
    return f"<b>Hello {name}!</b>"
```