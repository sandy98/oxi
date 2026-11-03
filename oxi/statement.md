
Yes, now we go to that, but first off I'd like to clarify the big picture of this project so you have enough elements to propose how the README could be configured.

1) Servers: there are 3 of them, each of them able to run standalone.
   a) server.jl: a fast Julia static/asgi/wsgi server that can run standalone as a statics asset server, or be provided with a Uvicorn-style command line argument, (i.e. apps.demo:app), in which case it will attempt to load the Python app using PythonCall, and upon success it will spawn server.py in a separate process, achieving IPC through a Unix socket. Handles by itself static assets at near C speed, and when it can't link the request path to a static resource it will hand the request dictionary and the socket itself (OOB) to server.py using the Unix socket. From that point on server.py handles the app (asgi or wsgi) for the request.
   b) webserver.cpp (I think it should be renamed to just server.cpp, and compile to server), compiles to webserver. This is a C++ speed static/asgi/wsgi server that mimics it's julia counterpart behaviour, but with very different  inner workings, the fundamental difference being that Python's code from server.py runs embedded in-process, thus achieving astonishing fast performance. It's worth noting that server.jl and webserver.cpp (and also server.py when running standalone) are cgi-enabled (including PHP) out of the box, without any complex configuration.
   c) server.py: this is a Python asgi/wsgi server that can run standalone or act  as the asgi/wsgi handler for a) or b). When it runs standalone, it has no static assets serving capabilities, unless static.py's static_app is somewhere in the "execution line". static.py is the Python only solution for serving static files. For example:
   python3 server.py static:static_app
   or:
   demo.py
   from oxi.app import  OxiApp
   from oxi.static import static_app

   app = OxiApp("Demo")
   app.next = static_app

   # This way, when app is served, it will delegate on static the search for static assets, including cgi, php and all.

   server.py provides handlers for http and websocket requests, that is , is websocket and sse enabled.
2) App: this is found in app.py which exports OxiApp, a standard compliant ASGI app, inherits from tina.tinapp.TinApp, which provides all the basic functionality of an asgi app (Flask like routing made easier, built-in session handling, external apps mounting, built-in simple templating engine, among others).  OxiApps adds lifespan handling to the mix.

Summing up, all this provides an extremely flexible and fast framework which allows the app developer a lot of possibilities when the time comes to choose:
OxiApp/Starlette/FastApi/Flask/Django running under server.jl, webserver or server.py
OxiApp running under uvicorn/daphne/granian
At the end of the day: great power with no framework locking.
