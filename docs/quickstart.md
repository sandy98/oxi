## 1. Installation

OxiServer is distributed as a standard Python package. It is highly recommended to install it inside a virtual environment.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install OxiServer
pip install oxi
```

(Optional) For a performance boost on the pure Python engine, install uvloop:

```bash
pip install "oxi[uvloop]"
```

## 2. See it in action (The Demo)

The fastest way to see what OxiServer can do is to run the built-in demo. This command creates an isolated temporary workspace, launches a fully functional application (with ASGI routing, CGI, and static files), and cleans up after you stop it.

```bash
rundemo
```

Open your browser and navigate to http://localhost:8086. Press Ctrl+C in your terminal to stop the server.

## 3. Create your own project.

```bash
scaffolding my_app
cd my_app
```

The generated `app.py` is a standard ASGI application:

```python
from oxi.app import OxiApp

app = OxiApp("My Oxi App")

@app.get("/")
async def home():
    return "Hello World!"
```

Run your new project using Oxi server:

```bash
oxiserver app:app
```

## 4. Compile the C++ Engine (Optional)

OxiServer ships with a fully functional Python server out of the box. However, if you want maximum performance (up to 1.45 GB/sec for static files, and embedded Python for dynamic routes), you can compile the bundled C++ engine.
```bash
oxibuild
```

The `oxibuild` command will automatically detect your C++ compiler. If you have a C++23 compatible compiler (like GCC 14+ or Clang 16+), it will compile the server binary in seconds.

(Note: On Ubuntu 22.04, you may need to install GCC 14. The oxibuild script will provide exact instructions if your compiler is too old).

Once compiled, `oxiserver` will automatically detect and use the C++ engine:

```bash
oxiserver app:app
```

## 5. Running the different server engines.

OxiServer is a polyglot engine. You can force the server to run on a specific engine using CLI flags:

```bash
# Run using the default engine (defaults to C++ engine if it is built, otherwise executes Python engine)
oxiserver app:app

# Run using the C++ engine (requires `oxibuild` first)
oxiserver app:app --cpp

# Run using the pure Python engine (default fallback)
oxiserver app:app --python

# Run using the Julia engine (requires Julia to be installed)
oxiserver app:app --julia
```

## 6. Next steps

*   Read the {doc}`Architecture Guide <architecture>` to understand how the C++ and Python engines communicate.
    
*   Learn how to use the {doc}`OxiApp Framework <oxiapp>` for routing http/websocket/sse requests, session handling, lifespan hooks, and mounting ASGI/WSGI apps, among a ton of out of the box built-in goodies.

