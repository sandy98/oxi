# -*- coding: utf_8 -*-

# pyright: reportMissingImports=false
# pyright: reportGeneralTypeIssues=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportFunctionMemberAccess=false
# pyright: reportReturnType=false
# pyright: reportArgumentType=false
# pyright: reportOptionalIterable=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportPossiblyUnboundVariable=false
# pyright: reportAssignmentType=false
# pyright: reportCallIssue=false


import threading, json, asyncio, time, os, multiprocessing, random

try:
    from tinaserver import TinaHandler, strftime_template, SmartDict
    from tinapp import TinApp, TinAException
    from websocket import WebSocket, CONNECTED
except:
    from tina.tinaserver import TinaHandler, strftime_template, SmartDict
    from tina.tinapp import TinApp, TinAException
    from tina.websocket import WebSocket, CONNECTED

######################################################################################

def test_app():
    app = TinApp()

    tlock = threading.Lock()

    from template import Menu, NavBar, MenuItem, MenuSep, DropdownMenu, Head, Body, HTMLApp, render_template 
    try:
        from examples import bicchiere, tinyapp #, starlette_app 
    except:
        pass
    try:
        tinyApp = tinyapp.tinyapp
    except:
        tinyApp = None
    
    #starletteApp = starlette_app.starlette_app
    try:
        bapp = bicchiere.demo_app()
    except:
        bapp = None
    try:
        from asgi_canonical import application as acanonical
        from wsgi_canonical import application as wcanonical
    except:
        acanonical = None
        wcanonical = None
    if tinyApp:
        app.mount(tinyApp, '/tinyapp')
    if acanonical:
        app.mount(acanonical, '/acanonical')
    if wcanonical:
        app.mount(wcanonical, '/wcanonical')
    #app.mount(starletteApp, '/starlette_home')
    #app.mount(starletteApp, "/starlette_hello", "/hello/Sandy")
    if bapp:
        app.mount(bapp, '/bicchiere')
        app.mount(bapp, '/bicchiere_about', '/about')
        app.mount(bapp, '/bicchiere_hello', '/hello')
        app.mount(bapp, '/bicchiere_cgi', '/progs_cgi')
        app.mount(bapp, '/bicchiere_session', '/showsession')
        app.mount(bapp, '/bicchiere_cookies', '/showcookies')


    staticApps = DropdownMenu(
        "Static content", 
        [
            MenuItem("Index", "/index.html"),
            MenuItem("Text", "/txt"),
            MenuItem("Images", "/img"),
            MenuSep(),
            MenuItem("Google (Redirection)", "/google"),
            MenuItem("Wikipedia (Redirection)", "/wikipedia"),
            MenuItem("Tiobe Languages (Redirection)", "/tiobe"),
            MenuSep(),
            MenuItem("Coronando Reyes (Reverse Proxy)", "/coronando")

        ])
    
    bicchiereApps = DropdownMenu(
        "Legacy Bicchiere Demo", 
        [MenuItem("Bicchiere Home (WSGI)", "/bicchiere"),
         MenuItem("Bicchiere About Page (WSGI)", "/bicchiere_about"), 
         MenuItem("Bicchiere Hello Page (WSGI)", "/bicchiere_hello"), 
         MenuItem("Bicchiere - CGI Apps (WSGI)", "/bicchiere_cgi"),
         MenuItem("Bicchiere Session Vars (WSGI)", "/bicchiere_session"), 
         MenuItem("Bicchiere - Cookies Handling (WSGI)", "/bicchiere_cookies"),
         ])

    testApps = DropdownMenu(
        "Mounted Test Apps", 
        [MenuItem("TinyApp (ASGI)", "/tinyapp"), 
         MenuItem("Asgi Canonical App - AKA Hello World (ASGI)", "/acanonical"),
         MenuItem("Wsgi Canonical App - AKA Hello World (WSGI)", "/wcanonical"),
        #  MenuItem("Starlette App - Home Page (ASGI)", "/starlette_home"),
        #  MenuItem("Starlette App - Hello Page (ASGI)", "/starlette_hello"),
         ])

    websocketApps = DropdownMenu(
        "WebSockets Examples",
        [
            MenuItem("Chatroom App (Featured!)", "/chatroom"),
            MenuItem("Echo App", "/echo")
        ])
    
    varsApps = DropdownMenu(
        "Forms, cookies and session vars",
        [
            MenuItem("Simulate login", "/login"),
            MenuItem("Handling form delivered by a web page", "/showurlencoded.html"), 
            MenuItem("Multipart form test", "/showmultipart.html"), 
            MenuItem("Built in form handling", "/uploader"),
            MenuSep(),
            MenuItem(f"Play with session vars {'' if app.session.get('user') else '(Requires login)'}", "/showsession"),
            MenuItem(f"View/handle Cookies {'' if app.session.get('user') else '(Requires login)'}", "/showcookies")
        ])

    madApps = DropdownMenu(
        "Nonsense things put here just to show how to handle errors.",
        [
            MenuItem("Go to nowhere...", '/willfind'),
            MenuItem("And this is plainly wrong!", "/wrong"),
            MenuItem("Even worse...", '/other')
        ]
    )

    assortedApps = DropdownMenu(
        "Assorted Stuff", 
        [MenuItem("Yet another Demo App", "/tinademo"),
         MenuSep(),
         MenuItem("See the greatest! (JSON response)", "/teams/1"),
         MenuItem("Or see them all... (JSON response)", "/teams"),
         MenuSep(),
         MenuItem("Easter egg No 1 (hint: 'this')", "/this"),
         MenuItem("Easter egg No 2 (you guess ...)", "/would"),
         MenuSep(),
         MenuItem("Show time (Server Sent Events example)", "/showtime"),
         MenuItem("Sum 7 and 35 and get magic response...", "/suma/7/35"), 
         MenuItem("Factorial of the magic number 42", "/factorial/42"), 
         MenuItem("Canvas example", "/circle_area/200"),
         MenuSep(),
         MenuItem("Download cutie kids picture for free!", "/chicos"),
         MenuItem("Server details", "/details"),
         MenuSep(),
         madApps
         ])

    navBar = NavBar("TinA Demo App", [
        MenuItem("Home", "/"),
        staticApps,
        websocketApps,
        testApps,
        bicchiereApps,
        varsApps,
        assortedApps,
        MenuItem("About", "/about")
    ])

    navBar.setBackground(random.choice(['#6f6f6f', '#008f00', '#00008f']))

    head = Head("Tina Demo App")
    htmlcontent = str(HTMLApp(head=head, body=Body(navBar)))

##############################################################################################################
    
    @app.sse('/ssetime')
    async def timegen():
        while True:
            await asyncio.sleep(1)
            yield 'event: timeinfo\ndata: {}\n\n'.format(time.strftime("%X"))

    @app.get('/showtime')
    async def showtime():
        contents=f'''
        <style>
            .clock {{
                padding-top: 1em;
                padding-bottom: 1em; 
                border-radius: 8px; 
                color: white; 
                background: {navBar.mB}; 
              /*  float: right;  */
                margin: 2rem;
                margin-bottom: 0.5rem;
                text-align: center;
                 width: 33%; 
                 max-width: 33%;
            }}
            .centered {{
                display: flex;
                flex-direction: row;
                justify-content: center;
            }}
        </style>
        <p>&nbsp;</p><p>&nbsp;</p><p>&nbsp;</p>
        <div class="centered">
            <h1 
                id="clock" 
                class="clock"
            >
                Server time:
            </h1>
        </div>
        <p>&nbsp;</p><p>&nbsp;</p><p>&nbsp;</p>
        <div class="centered">
            <h1 
                id="lclock" 
                class="clock"
            >
                Browser time:
            </h1>
        </div>
        <script>
            const pad = (str, len) => {{
                str = str.toString();
                const dif = len - str.length;
                if (dif <= 0) return str;
                return "0".repeat(dif) + str;
            }}
            const getltime = () => {{
                d = new Date();
                return `${{pad(d.getHours(), 2)}}:${{pad(d.getMinutes(), 2)}}:${{pad(d.getSeconds(), 2)}}`;
            }}
            const serverclock = document.getElementById('clock');
            const localclock = document.getElementById('lclock')
            let eSrc;
            const start_sse  = () => {{ 
                eSrc = new EventSource("/ssetime");
                eSrc.addEventListener('timeinfo', e => {{ 
                    serverclock.textContent = 'Server time: ' + e.data;
                    localclock.textContent = 'Browser time: ' + getltime(); 
                    }});
            }}
            start_sse();
            window.onbeforeunload = () => eSrc.close()
            // window.onfocus = () => start_sse();
        </script>
        '''
        return render_template(htmlcontent, contents=contents)

    @app.get("/about")
    async def about_page():
        about = '''
        <style>
            p {{
                font-size: 1.5em;
             /*   min-height: 0.5em;
                height: 1.30em; 
                padding: 5px; */
            }}
            a {{
                text-decoration: none;
                font-weight: bold;
                color: steelblue;
            }}
        </style>
        <h1 style="margin: 0.5em; font-family: sans-serif; font-size: 350%; text-align: center; color: {};">
            <span style="padding: 2px; text-shadow: 12px 5px 10px grey;">All about TinA (Tiny Asynchronous Web Server/App).</span>
        </h1>
        <hr>
        <p>
            TinA was born out of the idea of creating a pure Python/standard lib only ASGI server. 
            In turn, this idea was heavily influenced by the wonderful concepts and remarkable implementation
            exposed by <a href="https://github.com/eduardovra">Eduardo Vieyra</a> in these series:
        </p>
        <p>
            <a href="https://eduardovra.github.io/writing-a-python-web-server-from-scratch-part-1-http/">Writing a Python Web Server From Scratch - Part 1: HTTP</a>
        </p>
        <p>
            <a href="https://eduardovra.github.io/writing-a-python-web-server-from-scratch-part-2-websocket/">Writing a Python Web Server From Scratch - Part 2: WebSocket</a>
        </p>
        <p>
            In spite of its origin as a learning tool, goal that still stands, TinA proved to be fast and efficient, hence the
            desicion to offer it as a new alternative in the Python server/framework landscape.
        </p>
        '''.format(navBar.mB)

        return render_template(htmlcontent, contents=about)

    @app.route('/showcookies', methods=['GET', 'POST'])
    @app.login_required()
    async def showcookies():
        if app.method.upper() == 'POST':
            app.set_cookie(app.form.get('key'), app.form.get('value'), app.form.get('max_age'))
            await app.redirect("/showcookies")
        retstr = f"<!--<h1>SID: {app.get_cookie('sid') or 'null'}</h1><hr>-->"
        for k, v in app.get_cookies():
            k = k.decode()
            v = v.decode()
            if (k != 'sid' and k != '_sid' and k != 'id'):
                retstr += f"<p><span style='color: steelblue;'>{k}</span> = <span>{v}</span></p>"
        retstr += f"<hr><p>Cookie request header: {TinaHandler.get_request_header(app.scope, 'cookie')}</p><hr>"
        retstr += """
        <script>
            var p = document.createElement("p");
            p.textContent = "Browser document.cookie = " + document.cookie;
            document.body.appendChild(p);
        </script>
        <hr>
        """
        retstr += """<p>
            <form action="/showcookies" method="POST">
                <label>Set Cookie Key:&nbsp;</label><input type="text" name="key" required />
                <label>Cookie Value:&nbsp;</label><input type="text" name="value" />
                <label>Cookie Max Age (0 to delete cookie):&nbsp;</label><input type="number" value="10" name="max_age" required />
                &nbsp;<input type="submit" value="Set" />
            </form>
        </p>
        <hr>&nbsp;<p><button onclick="location.href = location.href;">Reload</button>&nbsp;&nbsp;
        &nbsp;<button onclick="location.href = '/';">Home</button></p>
        """
        return render_template(htmlcontent, contents=retstr)
    
    @app.post('/delsessionkey')
    @app.login_required()
    async def delsessionkey():
        form = app.form.copy()
        app.del_session_value(app.session, form.get('key'))
        # return '<script>location.href = "/showsession";</script>'
        await app.redirect('/showsession')

    @app.route('/showsession', methods=['GET', 'POST'])
    @app.login_required()
    async def showsession():
        form = None
        if app.method.upper() != 'GET':
            form = app.form.copy()
        if app.method.upper() == 'POST':
            app.set_session_value(app.session, form.get('key'), form.get('value'))

        retstr = "<hr>"
        for k in app.session:
            if (k != 'sid' and k != '_sid' and k != 'id'):
                retstr += f"<p><span style='color: steelblue;'>{k}</span> = <span>{app.session[k]}</span></p>"
        retstr += "<hr>"
        retstr += """<p>
            <form action="/showsession" method="POST">
                <label>Set Key:&nbsp;</label><input type="text" name="key" required />
                <label>Value:&nbsp;</label><input type="text" name="value" required />
                &nbsp;<input type="submit" value="Set" />
            </form>
        </p>"""
        retstr += "<hr>"
        retstr += """<p>
            <form action="/delsessionkey" method="POST">
                <label>Delete Key:&nbsp;</label><input type="text" name="key" required />
                &nbsp;<input type="submit" value="Delete" />
            </form>
            <hr>&nbsp;<button onclick="location.href = '/';">Home</button>
        </p>"""
        retstr += "<hr>"
        return render_template(htmlcontent, contents=retstr)

    @app.get('/chatroom')
    async def chat_home():
        # os.chdir(os.path.split(os.path.abspath(__file__))[0])
        path = 'static/chat.html'
        exists = os.path.exists(path)
        if not exists:
            path = 'chat.html'
        with open(path, 'r') as fd:
            # return fd.read().replace('<!--STYLE-->', TinaHandler.get_default_style())
            return render_template(htmlcontent, contents=fd.read())

    connections = []
    messages = []
    num_connected = multiprocessing.Value('i', 0)

    @app.websocket('/chat')
    async def do_some_chat(ws: WebSocket):  
        nonlocal num_connected 

        async def send_connected_list():
            userslist = list(filter(lambda name: name is not None, map(lambda conn: conn.username, connections)))
            await send2all({'type': 'users.list', 'list': userslist})

        async def send2all(msg: dict):
            dirty_list: bool = False
            for conn in connections:
                try:
                    if len(msg) and (conn.application_state == CONNECTED):
                        await conn.send_json(msg)
                        print(f"Sent message: '{msg.get('message', '')}' from {msg.get('user', '')} to {conn.name}")
                    else:
                        connections.remove(conn)
                        dirty_list = True
                except Exception as exc:
                    msg = f"\nCouldn't send message to client {conn.name} due to error: {exc.__class__.__name__}: {exc}"
                    print(msg)
                    try:
                        conn.close()
                    except:
                        pass
                    connections.remove(conn)
                    dirty_list = True
            
            if dirty_list:
                await send_connected_list()

        def random_color():
            return random.choice(['#008000', '#0000FF', '#000080', '#808080']) 

        try: 
            await ws.accept()
        except:
            return
        
        with num_connected.get_lock():
            num_connected.value += 1
            ws.name = f"Conn-{str(num_connected.value).zfill(5)}"
        with tlock:
            connections.append(ws)
            print(f"\nConnection {ws.name} accepted.")
            # with mlock:
            for msg in messages[-100:]:
                try:
                    await ws.send_json(msg)
                    print(f"Sent message: '{repr(msg)}' to {ws.name}")
                except:
                    print(f"\nError sending previous messages to {ws.name}")
                    # ws.close()
                    connections.remove(ws)
                    return await send_connected_list()
        while True:
            msg: dict = None
            try:
                msg =await ws.receive_json()
            except:
                print(f"\nError receiving message in {ws.name}")
                # ws.close()
                connections.remove(ws)
                return await send_connected_list()

            print(f"Received {repr(msg)} from {ws.name}")
            if hasattr(msg, 'get'):
                msg_type = msg.get('type', None)
                if not msg_type:
                    continue
            else:
                continue
            if msg_type == 'chat.msg':
                msg.update({'user_conn': ws.name, 'color': ws.color if hasattr(ws, 'color') else random_color()})
                with tlock:
                    messages.append(msg)
                    await send2all(msg)
            elif msg_type == "register.user":
                ws.username = msg.get('user')
                ws.color = msg.get('color', random_color())
                msg.update({'color': ws.color})
                try:
                    await ws.send_json(msg)
                except:
                    print(f"\nError sending message in {ws.name}")
                    # ws.close()
                    connections.remove(ws)
                    return await send_connected_list()
                await send2all({'type': 'chat.msg', 'user': 'Admin', 'color': 'blue', 'message': f'Say hi to {ws.username}'})
                await send_connected_list()
            elif msg_type == "register.color":
                ws.color = msg.get('color', random_color())
                try:
                    await ws.send_json(msg)
                except:
                    print(f"\nError sending message in {ws.name}")
                    # ws.close()
                    connections.remove(ws)
                    return await send_connected_list()
                print(f"Register color change for {ws.name}/{ws.username} to {ws.color}")
            else:
                print(f"Received a message type I don't know: '{msg_type}'\nSending it to the bin.")
                # await ws.send_json(msg)

    @app.get("/echo")
    async def show_echo():
        html = """
                <!DOCTYPE html>
                <html>
                    <head>
                        <title>Chat</title>
                    </head>
                    <body>
                        <h1 style="text-align: center; color: steelblue;">TinA WebSocket Echo Server</h1>
                        <hr>
                        <ul id='messages'>
                        </ul>
                        <form action="" onsubmit="sendMessage(event)">
                            <input type="text" id="messageText" autocomplete="off" style="width: 50em; height: 2rem; min-height: 2rem;"/>
                            <button>Send</button>
                        </form>
                        <hr>
                        <p style="text-align: center;"><button onclick="location.href = '/';">Home</button></p>
                        <script>
                            // var ws = new WebSocket("ws://localhost:8410/ws_echo");
                            var ws = new WebSocket(location.origin.replace('http', 'ws') + '/ws_echo');
                            ws.onopen = () => ws.send("Hello, I'm the new WS client!");
                            ws.onmessage = function(event) {
                                try {
                                    if (!event.data.length) return;
                                    var messages = document.getElementById('messages');
                                    var message = document.createElement('li');
                                    message.innerHTML = event.data.replace(/\'(.+)\'/, '<span style="color: red; font-weight: bold;">$1</span>')
                                    //var content = document.createTextNode(event.data);
                                    //message.appendChild(content);
                                    messages.appendChild(message);
                                    document.body.scrollHeight = document.body.scrollTop;
                                } catch(e) {
                                    console.error(e);
                                }
                            };
                            function sendMessage(event) {
                                try {
                                    event.preventDefault();
                                    var input = document.getElementById("messageText");
                                    if (input.value.length) {
                                        console.log(`Sending ${input.value}\n`)
                                        ws.send(input.value);
                                        input.value = '';
                                    }
                                } catch(e) {
                                    console.error(e);
                                }
                            }
                        </script>
                    </body>
                </html>
        """
        return render_template(htmlcontent, contents=html)

    @app.websocket("/ws_echo")
    async def ws_endpoint(websocket: WebSocket):
        # websocket = WebSocket(app.scope, app.receive, app.send)
        await websocket.accept()
        # await asyncio.sleep(0.1)
        await websocket.send_text(f"Hello, welcome to TinA WS Echo!")
        while True:
            data = await websocket.receive_text()
            print(f"Received data from client: {data}")
            if (len(data)):
                await websocket.send_text(f"Received: '{data}' at {time.strftime(strftime_template)}")

    @app.get("/index")
    @app.get("/")
    def home():
        # body =  TinaHandler.get_default_style()
        body = ''
        body +=  '''
        <!--<h1 style="color: steelblue;">This is the poor man\'s ASGI App ... :-)</h1>
        <hr>-->
        <p style="text-align: center;">
            <img src="img/tina.png" />
        </p>
        <h3>Links you may visit within this app ...</h3>
        <hr>
        <p><a href="/echo">WebSocket Example 1: echo app</a></p>
        <p><a href="/chatroom">WebSocket Example 2: chat app&nbsp;&nbsp;<span class="red">Featured!</span></a></p>
        <hr>
        <p><a href="/showsession">Play with session vars. They will be there when you come back.</a></p>
        <p><a href="/showcookies">View cookies. Very dull.</a></p>
        <hr>
        <p><a href="/tinademo">Yet another Demo App...</a></p>
        <p><a href="/login">Simulate login</a></p>
        <p><a href="/showurlencoded.html">Handling form delivered by a web page</a><p>
        <p><a href="/suma/7/35">Sum and answer to all</a></p>
        <p><a href="/factorial/42">Answer to all factorial</a></p>
        <p><a href="/circle_area/150">Give me a radius and I will return you circle's surface</a></p>
        <p><a href="/chicos">Download cutie kids picture for free!</a></p>
        <p><a href="/teams/1">See the greatest! (JSON response)</a></p>
        <p><a href="/teams">Or see them all... (JSON response)</a></p>
        <p><a href="/details">Server details</a></p>

        <hr>
        <p><a href="/willfind">Go to nowhere...</a></p>
        <p><a href="/wrong">And this is plainly wrong!</a></p>
        <p><a href="/other">Even worse...</a></p>
        <hr>
        <p><a href="/base">Take a look at base app.</a></p>
        <hr>
        '''
        return render_template(htmlcontent, contents=body)
    
    @app.get("/details")
    async def details():
        body = f"""<p style="text-align: center; font-size: 150%; font-weight: bold; font-family: sans-serif; color: steelblue;">
            Server process: PID = <span style="color: #008000">{os.getpid()}</span> - 
            Name = <span style="color: #008000">{multiprocessing.current_process().name}/{threading.current_thread().name}</span>
            {'&nbsp;' * 3}Time: <span style="color: #008000">{time.strftime(strftime_template)}</span>
            {'&nbsp;' * 3}<button onclick="location.href = location.href;">Reload</button>
            {'&nbsp;' * 3}<button onclick="location.href = '/';">Home</button>
        </p>
        <hr>
        """
        return render_template(htmlcontent, contents=body)

    @app.get("/teams", content_type="application/json")
    # @app.get("/team/<id: int>", content_type="application/json")
    async def teams(id: int = 0) -> str:
        squadre = {
            1: {'name': "River Plate", 'titles': 73, 'quote': "The greatest of them all"},
            2: {'name': "Boca Juniors", 'titles': 74},
            3: {'name': "Racing Club", 'titles': 37},
        }
        if id == 0:
            return json.dumps(squadre)
        t = squadre.get(id)
        if not t:
            exc_text = f"Team identified by: {id} wasn't found"
            print(exc_text)
            raise TinAException(404)
        else:
            return json.dumps(t)

    @app.get("/suma")
    @app.get("/suma/<a: int>")
    @app.get("/suma/<a: str>/<b: float>")
    def suma(a=7, b=35):
        return render_template(htmlcontent, contents=f'''<h1 style="text-align: center; color: steelblue; font-family: Helvetica; margin-bottom: 1em;">
        Sum of {format(a, '.2f')} and {format(b, '.2f')} is: <span style="color: green; background: #eeeeee; padding: 5px; 
        font-family: monospace; font-size: 150%;">
        {format(a + b, '.2f')}</span>
        </h1>
        <p style="text-align: center;"><button onclick="location.href='/';">Home</button></p>
        ''')
    
    @app.get("/factorial/<n: int>")
    def factorial(n):
        import math
        return render_template(htmlcontent, contents=f'''<div 
        style="color: steelblue; font-family: Helvetica; margin-bottom: 0.5em; margin-top: 1em; margin-left: 1em; font-size: 130%;"
        >
            Factorial of &nbsp;<span style="color: red;">{n}</span>&nbsp;&nbsp; 
            is: <br/>
        </div>
        <div style="color: green; font-family: monospace; overflow-wrap: break-word; width: 80%; margin-left: 5%; margin-bottom: 1em;
        font-size: 150%; padding: 10px;
        border: solid 1px; border-radius: 6px"
        >
            {math.factorial(n)}
        </div>
        <p style="text-align: center;"><button onclick="location.href='/';">Home</button></p>

        ''')
        
    @app.get("/willfind")
    def notfound():
        raise TinAException(404)
    
    @app.get("/wrong")
    def wrong():
        raise TinAException(500)
    
    @app.get("/other")
    def other():
        raise Exception("Misterious error...")
    
    @app.get("/chicos", content_type="image/jpeg", content_disposition="attachment")
    def chicos():
        fd = open('static/img/chicos.jpeg', 'rb')
        return fd.read()
    
    @app.get("/login")
    def login():
        # body =  TinaHandler.get_default_style() + '''
        body = '''
        <form action="/login" method="POST">
        <p>
            <label for="txt_username">Username &nbsp; &nbsp;</label>
            <input type="text" id="txt_username" name="username" />
        </p>
        <p>
            <label for="txt_passwd">Password &nbsp; &nbsp;</label>
            <input type="password" id="txt_passwd" name="passwd" />
        </p>
        <p>
            <input type="submit" value="Submit" />
            <input type="reset" value="Reset" />
        </p>
        <form>
        <script>
            document.querySelector('form').action += location.search
        </script>
        '''
        return render_template(htmlcontent, contents=body)
    
    @app.post("/login")
    async def dologin():
        if 'done' in app.form and 'username' in app.form and 'passwd' in app.form:
            username = app.form.get('username')
            passwd = app.form.get('passwd')
            if len('username') >= 3 and len(passwd) > 3:
                user = SmartDict(username=username, passwd='***')
                app.set_session_value(app.session, 'user', user)
                await app.redirect(app.form.get('done', '/'))
                return b''
            else:
                if 'user' in app.session:
                    # del app.session.user
                    app.del_session_value(app.session, 'user')
                return render_template(htmlcontent, contents='''
                <!DOCTYPE html>
                <html>
                  <head><title>Wrong login</title></head>
                  <body>
                    <h3>Wrong login</h3>
                    <p style="text-align: center;">
                        <button onclick="history.back();">Back</button>
                        &nbsp;&nbsp;<button onclick="location.href='/';">Home</button>
                    </p>
                    <script>
                        alert("Wrong username and or password.\nUser data has been erased from session.");
                        location.href="/";
                    </script>
                  </body>
                </html>
                    ''')
        # body = TinaHandler.get_default_style()
        body = ''
        for d in [app.form]:
            body += "<hr>" if len(d) else ''
            for k, v in d.items():
                body += f'<p><span class="steelblue">{k}</span> = <span>{v}</span><p>'
        body += "<hr>"
        body += '''
        <p style="text-align: center;">
            <button onclick="history.back();">Back</button>
            <button onclick="location.href='/';">Home</button>
        </p>'''

        return render_template(htmlcontent, contents=body)
    
    @app.get("/base")
    async def base():
        app.scope.update(path="/")
        return b''

    @app.get("/circle_area")
    def circle_area(r: float):
        import math, random
        colors = ['"#ff0000"', '"#008800"', '"#0000ff"', '"#ff8800"']
        color = random.choice(colors)
        return render_template(htmlcontent, contents=f'''<h1 style="margin-bottom: 1em; text-align: center; color: steelblue; font-family: Helvetica;">
        Circle area for radius {format(r, '.2f')}  is: <span style="color: green; background: #eeeeee; padding: 5px; 
        font-size: 150%; font-family: monospace;">
        {format(math.pi * r * r, '.2f')}</span>
        </h1><div style="display: flex; flex-direction: row; justify-content: center;">
        <div style="padding: 10px; display: flex; flex-direction: row; justify-content: center; 
        min-width: 50em, width: 50em; max-width: 50em; 
        min-height: 620px; margin-left: 2%; border: solid 1px; border-radius: 12px;">
            <canvas width=600 height=600 style="background: #ffffff;"></canvas>
        </div></div>
        <p style="text-align: center;"><button onclick="location.href='/';">Home</button></p>
        <script>
            const canvas = document.querySelector("canvas");
            const context = canvas.getContext('2d');
            context.fillStyle = {color};
            context.arc(300, 300, {r if r < 280 else 280}, 0, 2 * Math.PI);
            // context.stroke();
            context.fill();
        </script>
        ''')

    return app
