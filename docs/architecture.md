
Architecture
============

OxiServer is not just a web server; it is a **polyglot web ecosystem**. To achieve performance that rivals Nginx while maintaining the flexibility of Python, OxiServer uses a unique three-tier architecture.

The Three Tiers
---------------

When a request arrives at the server, it flows through three distinct layers:

1. **The C++ Fast Path (Static & CGI)**
2. **The Python Offload (ASGI/WSGI)**
3. **The Zero-Copy Socket Handoff**

Here is how they work together.

### 1\. The C++ Fast Path

If a request is for a static file (like an image, CSS, or HTML file) or a CGI script (like PHP or a `.sh` file), the C++ engine handles it entirely on its own.

* **Static files** are served using the Linux `sendfile()` syscall. This is a **zero-copy** operation, meaning the file goes directly from the filesystem cache to the network socket, completely bypassing userspace memory. This is why OxiServer can achieve transfer speeds of **1.45 GB/sec**.
* **CGI scripts** are executed using `posix_spawn()`. The C++ engine pipes the request body directly to the script's stdin and streams the output back to the client, parsing HTTP headers and `Status:` codes on the fly.

### 2\. The Python Offload

If a request is _not_ a static file (for example, a dynamic API route like `/api/users`), the C++ engine stops and looks for a Python application.

Instead of proxying the request over HTTP to a separate Python process (which is what Nginx + Gunicorn does), OxiServer **embeds the CPython interpreter directly inside the C++ process**.

The C++ server hands the raw socket file descriptor to an `asyncio` event loop running on a dedicated background thread. From that moment on, Python owns the connection.

### 3\. The Zero-Copy Socket Handoff

This is the secret sauce. When C++ hands the file descriptor to Python, there is **no data copying** and **no network overhead**.

The Python application reads from and writes to the exact same socket that the C++ engine accepted. The Python `asyncio` loop processes the HTTP request, runs the ASGI application, and sends the response directly back to the client.

Once the response is complete, the socket is closed by Python, and the C++ server is notified (via an atomic counter) that the thread is free.

The Polyglot Engines
--------------------

What makes OxiServer unique is that you can swap out the execution engine at runtime without changing a single line of Python code.

### The C++ Engine (`server`)

The flagship engine. It uses embedded CPython for dynamic routes and zero-copy `sendfile` for static assets. It is designed for maximum production performance.

### The Julia Engine (`server.jl`)

A high-performance engine written in Julia. Unlike the C++ engine (which embeds Python), the Julia engine spawns a separate Python worker process and communicates with it via a **Unix domain socket** using `SCM_RIGHTS` to pass file descriptors. This is ideal for scientific computing or REPL-driven development.

### The Python Engine (`server.py`)

A pure Python `asyncio` server. It has zero external dependencies (other than the standard library) and works everywhere Python runs. It is the fallback engine and the most portable option.

The ASGI Lifespan Protocol
--------------------------

OxiServer is fully compliant with the ASGI Lifespan protocol. When a Python application is loaded, the C++ engine sends a `lifespan.startup` event and **blocks the socket from binding** until the application sends `lifespan.startup.complete`.

If the app fails to start (e.g., a database connection fails), the server exits cleanly with code `1`. This ensures that your server never accepts requests before it is fully ready.

Why this Architecture?
----------------------

Most Python web servers (like Uvicorn or Gunicorn) are single-language. They do everything in Python, which means they are bottlenecked by the GIL and Python's memory management.

OxiServer is different. It delegates the "heavy lifting" (networking, static file I/O, process spawning) to a compiled language, and only uses Python for what it is best at: writing your application logic.

---
