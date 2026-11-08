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
            app.session.set_value("user", {"username": usr, "pwd": "secret"})
            return {"status": "User created"}
        else:
            await app.error(403, "Bad user and/or password")
    except:
        await app.error(400, "Malformed request")
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

Utilities: Forms, Headers, and Cookies
--------------------------------------

Just like Bottle, OxiApp provides convenient access to request data through the `app` object. Because OxiApp is asynchronous, these values are populated at the start of the request cycle.
```python
@app.post("/login")
async def login():
    # Direct access to form data
    user = app.form.get("user", "")
    pwd = app.form.get("pwd", "")

    if user == "admin" and pwd == "secret":
        return "Logged in!"
    
    return "Invalid credentials"
```

You can also access headers and cookies directly:

*   `app.headers.get("Content-Type")`
    
*   `app.cookies.get("session_id")`

Lifespan Hooks
--------------

OxiApp natively supports the ASGI Lifespan protocol. This allows you to run setup and teardown logic (like connecting to a database) before the server starts accepting requests, and clean up gracefully when the server shuts down.

```python
@app.on_startup
async def connect_db():
    print("🚀 Connecting to database...")
    # await db.connect()

@app.on_shutdown
async def disconnect_db():
    print("🔌 Closing database connection...")
    # await db.disconnect()
```
If a startup hook fails, the server will abort and exit with code `1`, preventing your server from accepting traffic in a broken state.


Mounting Sub-Applications
-------------------------

One of the most powerful features of OxiApp is the ability to mount other WSGI or ASGI applications under a specific path prefix. This allows you to compose complex applications from smaller, independent pieces.
```python
import asyncio
from flask import Flask
from oxi.app import OxiApp
from oxi import server

# Your main OxiApp
app = OxiApp("Main App")

@app.get("/")
async def home():
    return """
    <h1>Home Page</h1>
    <p><a href="/flask_greeting">Flask Hello</a></p>
    """

# A legacy Flask (WSGI) app
flask_app = Flask(__name__)

@flask_app.route("/")
def flask_index():
    return "Hello from Flask!"

# Mount the Flask app under /admin
app.mount(flask_app, "/flask_greeting", "/")

def main():
    asyncio.run(server.run(app, port=8000))

if __name__ == '__main__':
    main()
```
Now, when a user visits `/admin`, the request is seamlessly routed to the Flask app, while everything else is handled by OxiApp.

The Next Sub-Application
-------------------------

A somewhat related concept to mounting is setting the "next" application in the call chain. The difference is that a "mounted" app will be
invoked when the user targets a specific URL (i.e. `/flask_greeting` in the previous example), while in the chaining scenario the main app will traverse all its routes for a URL match and finally will delegate the task to its next application, which in turn will do the same until finding a matching URL or failing with 404.
A common scenario for this is OxiApp using static.static_app as its next handler, which can come handy when Oxi is running in a Python-only environment, without Julia (for `server.jl`) or the binary server to server static assets. The following Python snippet depicts this (taken from the demo app provided with Oxi (remember `rundemo`))
```python
from oxi.app import OxiApp
from oxi.static import static_app

app = OxiApp("Oxi Demo App")
app.next = static_app
```
