module OxiServer

Base.isdigit(s::AbstractString) = all(map((x::Char) -> isdigit(x), [c for c in s]))
Base.in(needle::AbstractString, haystack::AbstractString) = occursin(needle, haystack)

using Sockets
using Dates
using SHA
using Base64
import Base.Threads

try
    using JSON  
    using PythonCall
catch e
    println(stderr, "❌ Critical: Missing required packages. Will attempt to install:\n\n   import Pkg; Pkg.add([\"JSON\", \"PythonCall\"])\n")
    import Pkg
    try
        Pkg.add("JSON")
        Pkg.add("PythonCall")
        using JSON
        using PythonCall
    catch
        println(stderr, "❌ Critical: Failed to install required packages. Please install them manually.")
    end
end

function encode_image(image_data, image_type="image/jpeg")
    img_string = base64encode(image_data)
    return "data:$image_type;base64,$img_string"
end

sys = pyimport("sys")

filepath = abspath(PROGRAM_FILE)
parentpath = dirname(filepath)
grandparentpath = dirname(parentpath)
pyversion = ""
pyexecutor = ""

# options_virtual_env_path = "$parentpath/.options-virtual-env"
# examples_virtual_env_path = ""
# if isdir(options_virtual_env_path)
#     pyversion = readdir("$(options_virtual_env_path)/lib/")[begin]
#     pyexecutor = "$(options_virtual_env_path)/bin/python3"
#     options_virtual_env_path = "$(options_virtual_env_path)/lib/$(pyversion)/site-packages"
# else
#     examples_virtual_env_path = "$parentpath/.examples-virtual-env"
#     if isdir(examples_virtual_env_path)
#         pyversion = readdir("$(examples_virtual_env_path)/lib/")[begin]
#         pyexecutor = "$(examples_virtual_env_path)/bin/python3"
#         examples_virtual_env_path = "$(examples_virtual_env_path)/lib/$(pyversion)/site-packages"
#     end
# end

# if isdir(options_virtual_env_path) && !(options_virtual_env_path in sys.path)
#     sys.path.insert(0, examples_virtual_env_path)
# elseif isdir(examples_virtual_env_path) && !(examples_virtual_env_path in sys.path) && !(isdir(options_virtual_env_path))
#     sys.path.insert(0, options_virtual_env_path)
# end

if !(parentpath in sys.path)
    sys.path.insert(0, parentpath)
end
if !(grandparentpath in sys.path)
    sys.path.insert(0, grandparentpath)
end

if length(pyexecutor) > 0
    # println("Python executable is located at: $pyexecutor")
    ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
    # ENV["JULIA_PYTHONCALL_EXE"] = joinpath(dirname(abspath(PROGRAM_FILE)), ".examples-virtual-env", "bin", "python3")
    ENV["JULIA_PYTHONCALL_EXE"] = pyexecutor
end

# Reset code (turns off all styling)
RESET = "\033[0m"

# Foreground standard colors
BLACK   = "\033[30m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"


"""
Returns the absolute path of the directory containing the current Julia script.
"""
function base_dir()
#    joinpath(splitpath(abspath(PROGRAM_FILE))[begin:end-1])
    dirname(abspath(PROGRAM_FILE))
end

function current_dir()
    pwd()
end

# basedir = base_dir()

# if !(basedir in sys.path)
#     sys.path.insert(0, basedir)
# end

const PYTHON_APP = Ref{Union{Py, Nothing}}(nothing)
const UNIX_SOCKET_PATH = Ref{AbstractString}("/tmp/julia_python.sock")


py_socket = pyimport("socket")
py_struct = pyimport("struct")
py_json = pyimport("json")


"""
    prepare_ancillary_data(client_socket)

Extracts the raw file descriptor from a Julia socket, casts it to a native Cint,
and structures it into a standard POSIX SCM_RIGHTS payload readable by Python's recvmsg.
"""
function prepare_ancillary_data(client_socket)
    julia_raw_fd = fd(client_socket)
    native_int_fd = Base.cconvert(Cint, julia_raw_fd)
    anc_payload = py_struct.pack("i", native_int_fd)
    return [(py_socket.SOL_SOCKET, py_socket.SCM_RIGHTS, anc_payload)]
end

"""
Logs messages to diverse outputs
Examples:
  log_msg("Active server") # Writes to stdout
  log_msg("Crytical error", fp=stderr) # Writes to stderr
"""
function log_msg(msg::AbstractString; fp=stdout)
    # Clonamos de inmediato el contenido del texto para estabilizar 
    # la memoria capturada por la Task asíncrona
    mensaje_local = string(msg)
    @async begin
        println(fp, mensaje_local)
        flush(fp)
    end
end

"""
Reads config.json y transforms it in a global dictionary.
If file doesn't exist, provides an environment with safe default values.
"""
function load_config()
    ruta_config = joinpath(pwd(), "config.json")
    default_config = Dict{AbstractString, Any}()
    oxiversion = ""
    # Valores por defecto idénticos a tu especificación JSON
    try
        pyinit = pyimport("oxi")  # Aseguramos que el módulo Python esté cargado
        # println("Module $(string(pyinit)) imported correctly")
        oxiversion = pyinit.__version__  # Extraemos la versión desde Python
        pyconfig = pyinit.__config__  # Extraemos la configuración desde Python
        default_config = pyconvert(Dict{AbstractString, Any}, pyconfig)  
        default_config["version"] = string(oxiversion)  # Aseguramos que la versión sea un string
        # tempversion = string(default_config["version"])
        # println("default_config[\"version\"] is $tempversion")
    catch exc
        println("Se produjo un error: $(string(exc))")
        oxiversion = "0.0.1.DEBUG"
        default_config = Dict(
            "allow_cgi" => true,
            "allow_dirlisting" => true,
            "cgi_dir" => "cgi-bin",
            "chunk_size" => 8192,
            "index_files" => ["index.html", "index.htm", "index.php"],
            "log_dir" => "logs",
            "static_dir" => "static",
            "template_dir" => "templates"
        )
        default_config["version"] = oxiversion
        # tempversion = string(default_config["version"])
        # println("default_config[\"version\"] is $tempversion")
    end

    if isfile(ruta_config)
        try
            # JSON.parsefile abre el archivo y genera un Dict{String, Any} nativo
            config_data = JSON.parsefile(ruta_config)
            config_data["version"] = string(oxiversion)  # Aseguramos que la versión sea un string
            # println("Se cargó correctamente la configuración de archivo con la versión: $tempversion")
            return config_data
        catch e
            println(stderr, "⚠️ Error leyendo config.json, usando valores por defecto: $e")
            return default_config
        end
    else
        return default_config
    end
end

const CONFIG = load_config()

staticdir = get(CONFIG, "static_dir", "static")
if !isdir(staticdir)
    if abspath(PROGRAM_FILE) == @__FILE__
        println(stderr, "⚠️ Alert: static directory '$staticdir' does not exist. Using base directory instead.")
    end
    staticdir = ""
    CONFIG["static_dir"] = staticdir
end

function save_config(config::Dict{String, String} = CONFIG)
    ruta_config = joinpath(pwd(), "config.json")
    open(ruta_config, "w") do f
        JSON.print(f, config)
    end
end

# Holds the absolute path of the discovered PHP binary, or nothing if unavailable
const PHP_BINARY_PATH = Ref{Union{String, Nothing}}(nothing)

"""
Probes the OS environment paths at startup to detect an available PHP execution engine.
Prioritizes php-cgi over standard php CLI wrappers.
"""
function probe_php_runtime()
    # Check for the ideal CGI bin interface first
    cgi_path = Sys.which("php-cgi")
    if cgi_path !== nothing
        PHP_BINARY_PATH[] = cgi_path
        log_msg("ℹ PHP Engine detected via system path: $cgi_path\n")
        return
    end

    # Fallback to the standard command line interpreter wrapper
    cli_path = Sys.which("php")
    if cli_path !== nothing
        PHP_BINARY_PATH[] = cli_path
        log_msg("ℹ PHP CLI fallback detected via system path: $cli_path\n")
        return
    end

    # No compatible binary discovered in the system environment
    log_msg("⚠️ Warning: No compatible PHP execution engine found (php-cgi/php). PHP routing will be disabled.")
end

probe_php_runtime()

# Declaramos el diccionario global que albergará los tipos MIME
const MIME_TYPES = Dict{String, String}()

"""
Inits MIME types dictionary from Python's standard library.
"""
function init_mime_types()
    try
        mimetypes = pyimport("mimetypes")
        # Forzamos a Python a inicializar sus tablas internas por si acaso
        mimetypes.init()
        
        # Extraemos el diccionario nativo types_map de Python
        py_map = mimetypes.types_map
        
        # Lo convertimos de golpe a un diccionario nativo de Julia para máxima velocidad de lectura
        for py_key in py_map
            ext = pyconvert(String, py_key)
            mime = pyconvert(String, py_map[py_key])
            MIME_TYPES[ext] = mime
        end
        
        # Agregamos manualmente un par de defaults comunes por si faltan en algunas distros
        if !haskey(MIME_TYPES, ".js")   MIME_TYPES[".js"] = "application/javascript; charset=utf-8" end
        if !haskey(MIME_TYPES, ".css")  MIME_TYPES[".css"] = "text/css; charset=utf-8" end
        if !haskey(MIME_TYPES, ".html") MIME_TYPES[".html"] = "text/html; charset=utf-8" end
        
    catch e
        println(stderr, "⚠️ Alerta: No se pudo cargar mimetypes de Python, usando defaults mínimos.")
        MIME_TYPES[".html"] = "text/html; charset=utf-8"
        MIME_TYPES[".css"]  = "text/css; charset=utf-8"
        MIME_TYPES[".js"]   = "application/javascript; charset=utf-8"
    end
end

init_mime_types()

function get_mime_type(ruta_archivo::String)
    ext = lowercase(splitext(ruta_archivo)[end])
    return get(MIME_TYPES, ext, "application/octet-stream")
end

# Declaramos el diccionario global que albergará los estados HTTP (Ej: 200 => "OK")
const HTTP_STATUSES = Dict{Int, String}()

"""
Inits HTTP statuses dictionary from Python's standard library.
"""
function http_statuses_init()
    try
        # Importamos el enumerador nativo de Python
        http_module = pyimport("http")
        HTTPStatus = pygetattr(http_module, "HTTPStatus")
        
        # Recorremos el enumerador para extraer cada código y su frase descriptiva
        for status in HTTPStatus
            codigo = pyconvert(Int, pygetattr(status, "value"))
            frase = pyconvert(String, pygetattr(status, "phrase"))
            HTTP_STATUSES[codigo] = frase
        end
        
    catch e
        println(stderr, "⚠️ Alerta: No se pudo cargar HTTPStatus de Python, usando defaults mínimos.")
        # Mapeo mínimo de contingencia por si el puente de CPython falla al arrancar
        HTTP_STATUSES[200] = "OK"
        HTTP_STATUSES[400] = "Bad Request"
        HTTP_STATUSES[403] = "Forbidden"
        HTTP_STATUSES[404] = "Not Found"
        HTTP_STATUSES[500] = "Internal Server Error"
        HTTP_STATUSES[501] = "Not Implemented"
    end
end

http_statuses_init()

asyncio = pyimport("asyncio")
        
# ctx = pydict()
# ctx["asyncio"] = asyncio

# py_coro_code = """
# def py_coro(func):
#     async def wrapper(*args, **kwargs):
#         return func(*args, **kwargs)
#     return wrapper
# """

# pyexec(py_coro_code, ctx)
# py_coro = ctx["py_coro"]
# jl_coro = py_coro ∘ pyfunc


function parse_http_request(client_socket)
    try
        # 1. Leemos las cabeceras completas de la petición hasta la línea vacía (\r\n\r\n)
        header_buffer = IOBuffer()
        while true
            linea = readline(client_socket, keep=true)
            write(header_buffer, linea)
            if linea == "\r\n" || linea == "\n" || isempty(linea)
                break
            end
        end
        
        raw_headers_str = String(take!(header_buffer))
        if isempty(strip(raw_headers_str))
            return nothing
        end

        # 2. Invocamos al parser centralizado de Python pasándole el bloque de texto
        oxipy = pyimport("server")
        req_py = oxipy.parse_http_raw_text(raw_headers_str)
        
        # Si Python determina que las cabeceras están corruptas, devolvemos :malformed
        if Bool(req_py == pyconvert(Py, nothing))
            return :malformed
        end
        
        # 3. Convertimos el diccionario retornado por Python para las aduanas locales de Julia
        # rbody = ""
        # rmethod = pyconvert(String, req_py["method"])
        # rpath = pyconvert(String, req_py["path"])
        # if lowercase(rmethod) in ["post", "put", "patch"]
        #     post_body_bytes = Vector{UInt8}
        #     read!(client_socket, post_body_bytes)
        #     rbody = String(post_body_bytes)
        #     println("\n\nPre-loading request data...\n\n")
        # end

        return (
            version = pyconvert(String, req_py["version"]),
            method = pyconvert(String, req_py["method"]),
            path = pyconvert(String, req_py["path"]),
            raw_path = pyconvert(String, req_py["raw_path"]),
            query_string = pyconvert(String, req_py["query_string"]),
            protocol = pyconvert(String, req_py["protocol"]),
            headers = pyconvert(Dict{String, Any}, req_py["headers"])
        )
    catch e
        return :malformed
    end
end

function get_styled_date()
    oxipy = pyimport("server")
    return pyconvert(String, oxipy.get_styled_date())
end

function get_scope(request, host, port, ip_final_cliente, headers_list)
    return pydict(
        type = "http",
        asgi = pydict(version = "3.0", spec_version = "2.3"),
        method = request.method,
        path = request.path,
        raw_path = pybytes(codeunits(request.raw_path)),
        query_string = pybytes(codeunits(request.query_string)),
        scheme = "http",
        client = pylist([pystr(ip_final_cliente), 0]),
        server = pylist([pystr(host), port]),
        headers = pylist(headers_list)
    )
end


"""
Handles the dynamic ASGI Python application route. 
Runs concurrently inside the Julia task loop.
DEPRECATED
"""
function handle_app(request, client_socket, client_ip, request_line)
    ### New version: offloading ASGI work to child Python process

    # Request
            # version = pyconvert(String, req_py["version"]),
            # method = pyconvert(String, req_py["method"]),
            # path = pyconvert(String, req_py["path"]),
            # raw_path = pyconvert(String, req_py["raw_path"]),
            # query_string = pyconvert(String, req_py["query_string"]),
            # protocol = pyconvert(String, req_py["protocol"]),
            # headers = pyconvert(Dict{String, Any}, req_py["headers"])
    # ==============================================================

    # println("\nHandling request for $(request.path)\n\n")

    dict_request = Dict(
        pairs(request)
    )
    
    if lowercase(request.method) in ("post", "put", "patch")
        # println("\nHandling $(request.method) request\n\n")
        try
            content_length_str = "0"
            for (k, v) in request.headers
                k_low = lowercase(k)
                if k_low == "content-length"
                    content_length_str = strip(v)
                end
            end
            content_length_int = parse(Int, content_length_str)
            # println("Reported request body length is: $content_length_int")
            post_body_bytes = Vector{UInt8}(undef, content_length_int)
            read!(client_socket, post_body_bytes)
            # println("Request body length: $(length(post_body_bytes))")
            # dict_request[:body] = base64encode(read(client_socket))
            dict_request[:body] = base64encode(post_body_bytes)
            # println("Got body request comprising $(length(dict_request[:body])) bytes.")
        catch exc
            log_msg("Disaster while loading request body: $exc")
        end
    else
        dict_request[:body] = pybytes(codeunits(""))
    end

    try
        # 1. GENERATE ANCILLARY DATA VIA THE NEW SUBROUTINE
        anc_data = prepare_ancillary_data(client_socket)
        
        # 2. Establish a pipeline over the Unix Domain socket highway
        py_conn = py_socket.socket(py_socket.AF_UNIX, py_socket.SOCK_STREAM)
        py_conn.connect(UNIX_SOCKET_PATH[])
        
        # 3. Convert text directly to primitive byte vector for execution speed
        jrequest = JSON.json(dict_request)
        # jrequest = JSON.json(request)
        py_msg_bytes = pybytes(codeunits(jrequest))
        # 4. Push packet + descriptor down the highway.
        py_conn.sendmsg([py_msg_bytes], anc_data)
        py_conn.close()
        
        # # 5 Close Julia's side TCP socket
        # close(client_socket)

    catch exc
        log_msg("\n\n[$(get_styled_date())] ❌ Critical: Couldn't send data to child Python process because of \n$(exc) \n\n")
        send_error_response(client_socket, 500, client_ip, request_line, msg=exc)
    end
    ### End of offloading
end

# ==============================================================================

"""
Determines if a file is mp3 or mp4
"""
function is_mp_file(web_path::AbstractString)
    local_file_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    ext = lowercase(splitext(local_file_path)[end])
    return isfile(local_file_path) && (ext == ".mp4" || ext == ".mp3")
end

"""
Industrial strength streaming (mp3, mp4) handler.
"""
function handle_mp_streaming(client_socket, web_path::AbstractString, client_ip::AbstractString, request_line::AbstractString, request)
    local_file_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    mime_type = get_mime_type(local_file_path)

    try
        total_file_size = filesize(local_file_path)
        
        # Buscar si el cliente solicita un rango específico de bytes
        range_header = ""
        for (k, v) in request.headers
            if lowercase(k) == "range"
                range_header = strip(v)
                break
            end
        end

        open(local_file_path, "r") do physical_file
            configured_chunk_size = CONFIG["chunk_size"]
            memory_buffer = Vector{UInt8}(undef, configured_chunk_size)

            # --- CASO A: PETICIÓN PARCIAL (HTTP 206 Partial Content) ---
            if !isempty(range_header) && startswith(range_header, "bytes=")
                try
                    # Formato esperado: "bytes=start-end" (ej: bytes=0- or bytes=100-200)
                    range_bytes_str = replace(range_header, "bytes=" => "")
                    range_parts = split(range_bytes_str, "-")
                    
                    start_byte = parse(Int, range_parts[1])
                    end_byte = total_file_size - 1 # Por defecto hasta el final del archivo
                    
                    if length(range_parts) > 1 && !isempty(range_parts[2])
                        end_byte = parse(Int, range_parts[2])
                    end

                    # Validaciones de seguridad de fronteras de bytes
                    start_byte = max(0, min(start_byte, total_file_size - 1))
                    end_byte = max(start_byte, min(end_byte, total_file_size - 1))
                    
                    bytes_to_send = end_byte - start_byte + 1

                    # Escribimos los encabezados oficiales de transmisión parcial
                    write(client_socket, "HTTP/1.1 206 Partial Content\r\n")
                    write(client_socket, "Content-Type: $(mime_type)\r\n")
                    write(client_socket, "Content-Length: $bytes_to_send\r\n")
                    write(client_socket, "Content-Range: bytes $start_byte-$end_byte/$total_file_size\r\n")
                    write(client_socket, "Accept-Ranges: bytes\r\n")
                    write(client_socket, "Connection: close\r\n")
                    write(client_socket, "\r\n")

                    # Posicionamos el puntero del archivo en el byte de arranque solicitado (POSIX seek)
                    seek(physical_file, start_byte)
                    
                    remaining_bytes = bytes_to_send
                    while remaining_bytes > 0 && !eof(physical_file)
                        current_chunk = min(configured_chunk_size, remaining_bytes)
                        bytes_read = readbytes!(physical_file, memory_buffer, current_chunk)
                        
                        if bytes_read <= 0 break end
                        
                        write(client_socket, view(memory_buffer, 1:bytes_read))
                        remaining_bytes -= bytes_read
                    end
                    
                    flush(client_socket)
                    log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" 206 $bytes_to_send")
                    return
                catch
                    # Si el parseo de rangos falla, hacemos fallback silencioso a descarga completa
                end
            end

            # --- CASO B: DESCARGA COMPLETA TRADICIONAL (HTTP 200 OK) ---
            write(client_socket, "HTTP/1.1 200 OK\r\n")
            write(client_socket, "Content-Type: video/mp4\r\n")
            write(client_socket, "Content-Length: $total_file_size\r\n")
            write(client_socket, "Accept-Ranges: bytes\r\n")
            write(client_socket, "Connection: close\r\n")
            write(client_socket, "\r\n")

            while !eof(physical_file)
                bytes_read = readbytes!(physical_file, memory_buffer, configured_chunk_size)
                if bytes_read < configured_chunk_size
                    write(client_socket, view(memory_buffer, 1:bytes_read))
                else
                    write(client_socket, memory_buffer)
                end
            end
            
            flush(client_socket)
            log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" 200 $total_file_size")
        end

    catch e
        if !(e isa Base.IOError)
            log_msg("❌ Error inside MP4 chunk engine: $e", fp=stderr)
            send_error_response(client_socket, 500, client_ip, request_line, msg=e)
        end
    finally
        try close(client_socket) catch end
    end
end

"""
Analyzes the parsed HTTP headers to detect an incoming WebSocket upgrade handshake.
Looks for the standard 'Upgrade: websocket' contract defined in RFC 6455.
"""
function is_websocket_upgrade(request)
    has_upgrade_ws = false
    has_connection_upgrade = false
    
    for (k, v) in request.headers
        k_low = lowercase(k)
        v_low = lowercase(v)
        
        # The connection header can contain multiple tokens like "keep-alive, Upgrade"
        if k_low == "upgrade" && v_low == "websocket"
            has_upgrade_ws = true
        elseif k_low == "connection" && contains(v_low, "upgrade")
            has_connection_upgrade = true
        end
    end
    
    return has_upgrade_ws && has_connection_upgrade
end


"""
b) Determines if a requested web resource exists physically inside the configured static directory.
"""
function is_static_resource(ruta_web::AbstractString)
    # CONFIG["static_dir"] maps to your "static" folder from config.json
    ruta_local = joinpath(pwd(), CONFIG["static_dir"], lstrip(ruta_web, '/'))
    return isfile(ruta_local) || isdir(ruta_local)
end

function is_static_file(ruta_web::AbstractString)
    # CONFIG["static_dir"] maps to your "static" folder from config.json
    ruta_local = joinpath(pwd(), CONFIG["static_dir"], lstrip(ruta_web, '/'))
    return isfile(ruta_local)
end

"""
b2) Determines if the local static path is a directory.
"""
function is_dir_resource(ruta_web::AbstractString)
    ruta_local = joinpath(pwd(), CONFIG["static_dir"], lstrip(ruta_web, '/'))
    return isdir(ruta_local)
end

"""
b2-1) Determines if the file is a CGI application based on extension or path.
"""
function is_cgi_app(ruta_web::AbstractString)
    ruta_local = joinpath(pwd(), CONFIG["static_dir"], lstrip(ruta_web, '/'))
    
    # Condition A: URL contains the cgi-bin directory
    contiene_carpeta_cgi = contains(ruta_web, "/" * CONFIG["cgi_dir"] * "/")
    
    # Condition B: Executable CGI extension extensions
    ext = lowercase(splitext(ruta_local)[2])
    es_extension_cgi = ext == ".py" || ext == ".sh" || ext == ".cgi" || ext == ".pl"
    es_extension_cgi = es_extension_cgi || ext == ".rb" || ext == ".java"
    return isfile(ruta_local) && (contiene_carpeta_cgi || es_extension_cgi)
end


"""
b2-3) Determines if the requested file corresponds to a PHP script based on its extension.
"""
function is_php(web_path::AbstractString)
    local_file_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    ext = lowercase(splitext(local_file_path)[end])
    return isfile(local_file_path) && ext == ".php"
end

"""
b2-3-1) Dynamically spawns a native OS 'php-cgi' process to execute PHP scripts.
Pipes incoming payload bodies to stdin and streams compiled outputs seamlessly to the wire.
"""
function handle_php(client_socket, 
    web_path::AbstractString, 
    client_ip::AbstractString, 
    request_line::AbstractString, 
    request)
    local_script_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    
    # 1. Strict validation of file existence before triggering the OS fork
    if !isfile(local_script_path)
        send_error_response(client_socket, 404, client_ip, request_line)
        return
    end

    try
        # Extract dynamic length metadata for incoming POST payloads
        content_length_str = "0"
        content_type_str = ""
        for (k, v) in request.headers
            k_low = lowercase(k)
            if k_low == "content-length"
                content_length_str = strip(v)
            elseif k_low == "content-type"
                content_type_str = strip(v)
            end
        end
        content_length_int = parse(Int, content_length_str)

        # 2. COMPILING RIGOROUS PHP-CGI MANDATORY ENVIRONMENT VARIABLES
        php_env = Dict{String, String}(
            "SERVER_SOFTWARE"   => "OxiServer/$(CONFIG["version"]) (C++/Julia Powered static/ASGI/WSGI Server)",
            "SERVER_NAME"       => "OxiServer/$(CONFIG["version"])",
            "GATEWAY_INTERFACE" => "CGI/1.1",
            "SERVER_PROTOCOL"   => string(request.protocol),
            "REQUEST_METHOD"    => string(request.method),
            "PATH_INFO"         => string(request.path),
            "SCRIPT_NAME"       => string(web_path),
            "SCRIPT_FILENAME"   => string(local_script_path), # Absolute physical filesystem target
            "REDIRECT_STATUS"   => "200",                     # Mandatory bypass safety switch for php-cgi
            "QUERY_STRING"      => string(request.query_string),
            "REMOTE_ADDR"       => string(client_ip),
            "CONTENT_LENGTH"    => content_length_str,
            "CONTENT_TYPE"      => content_type_str
        )

        # Inyectamos las headers HTTP estándar con el prefijo reglamentario
        for (k, v) in request.headers
            env_key = "HTTP_" * uppercase(replace(k, "-" => "_"))
            php_env[env_key] = string(v)
        end

        # 3. SPARKING THE EXECUTIVE RUNTIME PROCESS
        # We target 'php-cgi' directly, passing our secure environment map container
        # php_cmd = setenv(`php-cgi`, php_env)
        php_cmd = setenv(`$(PHP_BINARY_PATH[])`, php_env)
        php_process = open(php_cmd, "w+")
        
        try
            # STEP A: Pipe the incoming HTTP payload body directly into the PHP process stdin
            if content_length_int > 0 && isopen(client_socket)
                post_bytes = Vector{UInt8}(undef, content_length_int)
                read!(client_socket, post_bytes)
                write(php_process.in, post_bytes)
                flush(php_process.in)
            end
            close(php_process.in) # Send EOF signal to prevent execution lockup stalls

            # STEP B: Strict inspection of the first lines of data emitted by the PHP process
            if eof(php_process.out)
                send_error_response(client_socket, 502, client_ip, request_line, msg="PHP runtime process aborted without output headers.")
                return
            end

            # php-cgi handles headers perfectly, we read the initial status structure dynamically
            first_line_str = strip(readline(php_process.out))
            first_line_bytes = Vector{UInt8}(first_line_str * "\n")

            response_status_code = 200
            response_status_phrase = "OK"

            if startswith(lowercase(first_line_str), "status:")
                try
                    status_parts = split(first_line_str, ":", limit=2)
                    tokens = split(strip(status_parts[2]), " ", limit=2)
                    response_status_code = parse(Int, tokens[1])
                    response_status_phrase = length(tokens) > 1 ? string(tokens[2]) : "PHP CGI Output"
                catch
                    response_status_code = 200
                end
            end

            # Write standard prologue directly over the active wire socket channel
            if isopen(client_socket)
                write(client_socket, "HTTP/1.1 $response_status_code $response_status_phrase\r\n")
                
                # If the script omitted explicit protocol keys, enforce html standard metadata bounds
                if !startswith(lowercase(first_line_str), "status:") && !startswith(lowercase(first_line_str), "x-powered-by:") && !startswith(lowercase(first_line_str), "content-type:")
                    write(client_socket, "Content-Type: text/html; charset=utf-8\r\n")
                    write(client_socket, "Connection: close\r\n")
                    write(client_socket, "\r\n")
                    write(client_socket, first_line_bytes)
                else
                    write(client_socket, first_line_bytes)
                end
            end

            # Setup high-performance level 33 streaming chunk buffers
            configured_chunk_size = CONFIG["chunk_size"]
            memory_buffer = Vector{UInt8}(undef, configured_chunk_size)
            bytes_sent = length(first_line_bytes)

            while !eof(php_process.out)
                bytes_read = readbytes!(php_process.out, memory_buffer, configured_chunk_size)
                bytes_sent += bytes_read
                
                if bytes_read < configured_chunk_size
                    write(client_socket, view(memory_buffer, 1:bytes_read))
                else
                    write(client_socket, memory_buffer)
                end
            end
            
            flush(client_socket)
            log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" $response_status_code $bytes_sent")

        finally
            close(php_process) # Clear residual kernel file handles gracefully
        end

    catch e
        if !(e isa Base.IOError)
            log_msg("❌ Critical exception inside handle_php execution cluster: $e", fp=stderr)
            send_error_response(client_socket, 500, client_ip, request_line)
        end
    finally
        try close(client_socket) catch end
    end
end

"""
Dispatches a beautifully styled Nginx-like HTML error page to the client socket.
Maintains the precious monospace aesthetics established in the directory lister.
"""
function send_error_response(client_socket, 
    status_code::Int, 
    client_ip::AbstractString, 
    request_line::AbstractString; 
    msg="OxiServer was unable to process this request on the local runtime layer.")
    
    status_phrase = get(HTTP_STATUSES, status_code, "Error")
    
    # 1. Craft the clean, professional monospace HTML layout
    html_error_payload = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>$(status_code) $(status_phrase)</title>
        <style>
            body { font-family: 'monospace', sans-serif; margin: 3rem; background: #fafafa; color: #111; text-align: center; }
            .error-container { max-width: 600px; margin: 0 auto; background: white; padding: 2.5rem; border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #eaeaea; }
            h1 { font-size: 1.8rem; color: #cc3333; margin-top: 0; padding-bottom: 0.5rem; border-bottom: 1px solid #eaeaea; }
            p { font-size: 1.1rem; color: #333; line-height: 1.6; }
            .details { font-size: 0.9rem; color: #666; background: #f5f5f5; padding: 0.8rem; border-radius: 4px; text-align: left; word-break: break-all; margin-top: 1.5rem; }
            .footer { margin-top: 2.5rem; border-top: 1px solid #eaeaea; padding-top: 0.8rem; font-size: 0.85rem; color: #666; text-align: center; }
        </style>
    </head>
    <body>
        <div class="error-container">
            <h1>$(status_code) $(status_phrase)</h1>
            <p>$(msg)</p>
            <div class="details">
                <b>Client IP:</b> $(client_ip)<br>
                <b>Request:</b> $(request_line)<br>
                <b>Server Timestamp:</b> $(get_styled_date())
            </div>
        </div>
        <div class="footer">OxiServer/$(CONFIG["version"]) (C++/Julia Powered static/ASGI/WSGI Server)</div>
    </body>
    </html>
    """
    
    html_bytes = Vector{UInt8}(html_error_payload)
    payload_length = length(html_bytes)

    try
        if isopen(client_socket)
            # Emit strict HTTP/1.1 compliance packets
            write(client_socket, "HTTP/1.1 $status_code $status_phrase\r\n")
            write(client_socket, "Content-Type: text/html; charset=utf-8\r\n")
            write(client_socket, "Content-Length: $payload_length\r\n")
            write(client_socket, "Connection: close\r\n")
            write(client_socket, "\r\n") # Mandatory delimiter boundary
            
            write(client_socket, html_bytes)
            flush(client_socket)
        end
    catch
        # Fail silently if the socket pipe was dropped by the client browser
    end
    
    # Asynchronous logging call to protect high-concurrency throughput
    log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" $status_code $payload_length")
    try close(client_socket) catch end
end

"""
b2-1-1) Serves a static file using efficient streaming in chunks (Level 33).
Maintains low memory footprint regardless of file size by utilizing CONFIG["chunk_size"].
"""
function handle_send_file(client_socket, web_path::AbstractString, client_ip::AbstractString, request_line::AbstractString)
    local_file_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    
    try
        # Native high-performance file size lookup via kernel metadata
        total_file_size = filesize(local_file_path)
        mime_type = get_mime_type(local_file_path)
        charset = startswith(mime_type, "text/") ? "; charset=utf-8" : ""
        
        # 1. Emit standard HTTP/1.1 response headers
        write(client_socket, "HTTP/1.1 200 OK\r\n")
        write(client_socket, "Content-Type: $mime_type$charset\r\n")
        write(client_socket, "Content-Length: $total_file_size\r\n")
        write(client_socket, "Connection: close\r\n")
        write(client_socket, "\r\n") # Critical boundary blank line separator
        
        # 2. Open the asset file descriptor in an efficient read-stream block
        open(local_file_path, "r") do physical_file
            # Fetch the precise memory window boundary from config.json (8192 bytes)
            configured_chunk_size = CONFIG["chunk_size"]
            memory_buffer = Vector{UInt8}(undef, configured_chunk_size)
            
            # Streaming loop: pipe disk blocks straight into the network pipe
            while !eof(physical_file)
                bytes_read = readbytes!(physical_file, memory_buffer, configured_chunk_size)
                # If we read a partial block (the EOF trail), slice the buffer safely
                if bytes_read < configured_chunk_size
                    write(client_socket, view(memory_buffer, 1:bytes_read))
                else
                    write(client_socket, memory_buffer)
                end
            end
        end
        
        # Flush the kernel socket pipe upon successfully draining the file stream
        flush(client_socket)
        
        # Unified Nginx-style telemetric log entry
        log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" 200 $total_file_size")
        
    catch e
        # Absorb premature client drops gracefully without flooding the error log
        if !(e isa Base.IOError)
            log_msg("❌ Error inside handle_send_file chunk engine: $e", fp=stderr)
            send_error_response(client_socket, 500, client_ip, request_line, msg=e)
        end
    finally
        try close(client_socket) catch end
    end
end

"""
b2-1-2) Spawns a native OS subprocess to execute CGI scripts (.py, .sh, .pl).
Pipes client_socket POST body into cgi stdin, and streams cgi stdout back to the network.
"""
function handle_cgi(client_socket, 
    web_path::AbstractString, 
    client_ip::AbstractString, 
    request_line::AbstractString, 
    request)
    local_script_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    
    if !isfile(local_script_path)
        send_error_response(client_socket, 404, client_ip, request_line, 
        msg="<strong>$(web_path)</strong> is not a file")
        return
    end

    try
        # 1. Detect the appropriate script interpreter based on extension
        ext = lowercase(splitext(local_script_path)[end])
        interpreter = ""
        if ext == ".py"     interpreter = "python3"
        elseif ext == ".sh" interpreter = "bash"
        elseif ext == ".pl" interpreter = "perl"
        elseif ext == ".rb" interpreter = "ruby"
        elseif ext == ".java" interpreter = "java"
        else
            interpreter = "" # Supposedly a standalone executable but we'll see about that.
            # Read the file's owner permissions mask bits natively from Julia
            owner_permissions = uperm(local_script_path)
            
            # In POSIX systems, a value of 0x01 inside the owner mask represents EXECUTE permission (+x)
            is_executable = (owner_permissions & 0x01) != 0
            
            if !is_executable
                log_msg("⚠️ Security Warning: Blocked CGI execution on non-executable standalone file: $web_path")
                # 403 Forbidden is the formal HTTP status code for permission rejections
                send_error_response(client_socket, 403, client_ip, request_line, 
                msg="<strong>$(web_path)</strong> cannot be executed.")
                return           
            end
        end
        # Extract payload content headers if they exist in the incoming request
        content_length_str = "0"
        content_type_str = ""
        for (k, v) in request.headers
            k_low = lowercase(k)
            if k_low == "content-length"
                content_length_str = strip(v)
            elseif k_low == "content-type"
                content_type_str = strip(v)
            end
        end
        content_length_int = parse(Int, content_length_str)

        # 2. Build the official CGI/1.1 environment variables catalog
        cgi_env = Dict{String, String}(
            "SERVER_SOFTWARE"   => "OxiServer/$(CONFIG["version"]) (C++/Julia Powered static/ASGI/WSGI Server)",
            "SERVER_NAME"       => "OxiServer/$(CONFIG["version"])",
            "GATEWAY_INTERFACE" => "CGI/1.1",
            "SERVER_PROTOCOL"   => string(request.protocol),
            "REQUEST_METHOD"    => string(request.method),
            "PATH_INFO"         => string(request.path),
            "SCRIPT_NAME"       => string(web_path),
            "QUERY_STRING"      => string(request.query_string),
            "REMOTE_ADDR"       => string(client_ip),
            "CONTENT_LENGTH"    => content_length_str,
            "CONTENT_TYPE"      => content_type_str
        )

        # Inject standard HTTP_ prefixed environment headers
        for (k, v) in request.headers
            env_key = "HTTP_" * uppercase(replace(k, "-" => "_"))
            cgi_env[env_key] = string(v)
        end

        # Encapsulate command execution string together with its exclusive environment
        if interpreter == ""
            cgi_cmd = setenv(`$local_script_path`, cgi_env)
        else
            cgi_cmd = setenv(`$interpreter $local_script_path`, cgi_env)
        end
        # 3. BIDIRECTIONAL PROCESS FORK PIPING (Nivel 34):
        # "w+" flag opens the subprocess exposing BOTH .in (stdin) and .out (stdout) streams
    
        # 3. BIDIRECTIONAL PROCESS FORK PIPING (Level 34)
        cgi_process = open(cgi_cmd, "w+")
        
        try
            # STEP A: If the request is a POST/PUT with a body, flush those bytes into cgi stdin
            if content_length_int > 0 && isopen(client_socket)
                post_body_bytes = Vector{UInt8}(undef, content_length_int)
                read!(client_socket, post_body_bytes)
                write(cgi_process.in, post_body_bytes)
                flush(cgi_process.in)
            end
            close(cgi_process.in) # Signal EOF to the CGI script stdin

            # =====================================================================
            # STEP B: STRICT CGI HEADER INSPECTION & STREAMING (Fix CGI 2)
            # =====================================================================
            # Default response states if the script underperforms
            response_status_code = 200
            response_status_phrase = "OK"
            
            # Check if the process output stream has bytes available immediately
            if eof(cgi_process.out)
                # Script output is empty! Trigger a 502 Bad Gateway instead of a blind 200
                send_error_response(client_socket, 502, client_ip, request_line, 
                msg="<strong>$(web_path)</strong> did not send any content.")
                return
            end

            # Read strictly the first line emitted by the CGI script to validate the contract
            # first_line_bytes = readline(cgi_process.out, keep=true)
            # first_line_str = strip(String(copy(first_line_bytes)))
            first_line_str = strip(readline(cgi_process.out))
            first_line_bytes = Vector{UInt8}(first_line_str * "\n")

            # Parse the status code if the script explicitly provides a 'Status:' or 'HTTP/' header
            if startswith(lowercase(first_line_str), "status:")
                try
                    # Extract the tokens (e.g., "Status: 302 Found" -> "302")
                    status_parts = split(first_line_str, ":", limit=2)
                    tokens = split(strip(status_parts[2]), " ", limit=2)
                    response_status_code = parse(Int, tokens[1])
                    response_status_phrase = length(tokens) > 1 ? string(tokens[2]) : "CGI Response"
                catch
                    response_status_code = 200 # Fallback default
                end
            elseif startswith(lowercase(first_line_str), "http/")
                try
                    tokens = split(first_line_str, " ", limit=3)
                    response_status_code = parse(Int, tokens[2])
                    response_status_phrase = length(tokens) > 2 ? string(tokens[3]) : "CGI Response"
                catch
                    response_status_code = 200
                end
            end

            # Now that we are certain the script is communicating, emit the clean HTTP/1.1 prologue
            if isopen(client_socket)
                write(client_socket, "HTTP/1.1 $response_status_code $response_status_phrase\r\n")
                
                # If the first line was NOT a protocol header but actual content body payload,
                # we must inject a fallback content type and write those bytes back to the socket stream
                if !startswith(lowercase(first_line_str), "status:") && !startswith(lowercase(first_line_str), "http/")
                    write(client_socket, "Content-Type: text/html; charset=utf-8\r\n")
                    write(client_socket, "Connection: close\r\n")
                    write(client_socket, "\r\n") # Mandatory separator boundary
                    write(client_socket, first_line_bytes) # Restore the first line payload
                else
                    # The script started with a valid header line, pipe it directly
                    write(client_socket, first_line_bytes)
                end
            end
            
            # Setup standard level 33 chunk stream buffers for the remaining payload body
            configured_chunk_size = CONFIG["chunk_size"]
            memory_buffer = Vector{UInt8}(undef, configured_chunk_size)
            bytes_sent = length(first_line_bytes) # Account for the inspected first line
            
            while !eof(cgi_process.out)
                bytes_read = readbytes!(cgi_process.out, memory_buffer, configured_chunk_size)
                bytes_sent += bytes_read
                
                if bytes_read < configured_chunk_size
                    write(client_socket, view(memory_buffer, 1:bytes_read))
                else
                    write(client_socket, memory_buffer)
                end
            end
            
            flush(client_socket)
            
            # Log the true synchronized HTTP status code and metrics calculated
            log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" $response_status_code $bytes_sent")

        finally
            close(cgi_process) # Secure system process handles cleanup
        end

    catch e
        if !(e isa Base.IOError)
            log_msg("❌ Critical exception inside handle_cgi engine: $e", fp=stderr)
            send_error_response(client_socket, 500, client_ip, request_line, msg=e)
        end
    finally
        try close(client_socket) catch end
    end
end


"""
b2-2) Reads a local physical directory using readdir() and streams a 
dynamic HTML directory listing page back to the client socket (Nginx-style).
"""
function handle_send_dir(client_socket, web_path::AbstractString, client_ip::AbstractString, request_line::AbstractString)
    local_dir_path = joinpath(pwd(), CONFIG["static_dir"], lstrip(web_path, '/'))
    
    if !isdir(local_dir_path)
        send_error_response(client_socket, 404, client_ip, request_line,
        msg="<strong>$(web_path)</strong> is not a directory.")
        return
    end

    try
        # --- EXPLICIT SECURITY FIREWALL (CGI Directory Protection) ---
        # If the web path attempts to list the cgi-bin directory, block it immediately
        if occursin("/" * CONFIG["cgi_dir"], web_path) || occursin(CONFIG["cgi_dir"] * "/", web_path)
            log_msg("⚠️ Security Alert: Blocked directory listing attempt on CGI folder from $client_ip")
            send_error_response(client_socket, 403, client_ip, request_line,
            msg="<strong>$(web_path)</strong> listing is forbidden.")
            return
        end        
        # Native high-performance directory indexing from the OS kernel
        dir_contents = readdir(local_dir_path)
        # println(local_dir_path)
        dirs = filter((elem) -> isdir("$(local_dir_path)/$(elem)"), dir_contents)
        files = filter((elem) -> isfile("$(local_dir_path)/$(elem)"), dir_contents)
        sort!(dirs)
        sort!(files)
        directory_contents = []
        append!(directory_contents, dirs)
        append!(directory_contents, files)
        # Normalize the web path path display for the HTML header
        display_path = web_path == "" ? "/" : web_path
        if !endswith(display_path, "/") display_path = display_path * "/" end

        # 1. Start crafting the dynamic Nginx-style HTML payload
        html_payload = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Index of $(display_path)</title>
            <style>
                body { font-family: 'monospace', sans-serif; margin: 2rem; background: #fafafa; color: #111; }
                h1 { border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; font-size: 1.5rem; }
                ul { list-style: none; padding-left: 0; }
                li { margin: 0.4rem 0; }
                a { color: #0066cc; text-decoration: none; font-size: 1.1rem; }
                a:hover { text-decoration: underline; }
                .footer { margin-top: 2rem; border-top: 1px solid #ccc; padding-top: 0.5rem; font-size: 0.9rem; color: #555; }
            </style>
        </head>
        <body>
            <h1>Index of $(display_path)</h1>
            <ul>
        """

        # Inject a "Parent Directory" link if the user is inside a subfolder
        if display_path != "/"
            # Cleanly calculate the parent URI path slice
            parent_path = dirname(dirname(display_path))
            if parent_path == "" || parent_path == "." parent_path = "/" end
            html_payload *= "<li><a href=\"$(parent_path)\">📁 .. (Parent Directory)</a></li>"
        end

        # 2. Iterate over the filesystem items and append links to the layout
        for item in directory_contents
            # Skip hidden files starting with a dot (like .git, .env) for basic security
            if startswith(item, ".") continue end
            
            # Determine item visual icon badge by testing physical attributes
            full_item_path = joinpath(local_dir_path, item)
            icon_badge = isdir(full_item_path) ? "📁" : "📄"
            
            # Web browsers require directory links to terminate with a trailing slash
            item_link = isdir(full_item_path) ? item * "/" : item
            
            html_payload *= "<li>$icon_badge <a href=\"$(display_path)$(item_link)\">$item</a></li>"
        end

        # Append closing layout wrappers and signature metrics
        html_payload *= """
            </ul>
            <div class="footer">OxiServer/$(CONFIG["version"]) (C++/Julia Powered static/ASGI/WSGI Server)</div>
        </body>
        </html>
        """

        html_bytes = Vector{UInt8}(html_payload)
        payload_length = length(html_bytes)

        # 3. Emit official HTTP/1.1 response packages down the pipe
        write(client_socket, "HTTP/1.1 200 OK\r\n")
        write(client_socket, "Content-Type: text/html; charset=utf-8\r\n")
        write(client_socket, "Content-Length: $payload_length\r\n")
        write(client_socket, "Connection: close\r\n")
        write(client_socket, "\r\n")
        
        write(client_socket, html_bytes)
        flush(client_socket)

        # Log entry showing successful listing generation
        log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" 200 $payload_length")

    catch e
        if !(e isa Base.IOError)
            log_msg("❌ Critical exception inside handle_send_dir engine: $e", fp=stderr)
            send_error_response(client_socket, 500, client_ip, request_line)
        end
    finally
        try close(client_socket) catch end
    end
end

# ===============================================================================

function handle_conn(client_socket, python_app)
    # Variables locales para recopilar la métrica final estilo Nginx
    client_ip = "127.0.0.1"
    bytes_enviados = 0
    # response_status = 200
    request_line = "GET / HTTP/1.1"
    
    try
        request = parse_http_request(client_socket)
        
        if request === nothing
            close(client_socket)
            return
        elseif request === :malformed
            write(client_socket, "HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\n400 Bad Request.")
            log_msg("$(client_ip) - - [$(get_styled_date())] \"UNKNOWN / HTTP/1.1\" 400 0")
            close(client_socket)
            return
        elseif request.path == "/oxi_heartbeat"
            status_code = 418
            status_message = "I'm a teapot"
            write(client_socket, "HTTP/1.1 $(status_code) $(status_message)\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\n$(status_message)")
            log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"GET /oxi_heartbeat HTTP/1.1\" 418 $(length(status_message))")
            close(client_socket)
            return
        end

        # --- DETECCIÓN INTELIGENTE DE IP DETRÁS DE PROXY ---
        # Por defecto usamos la IP local del socket (o la IP que detecte Sockets.getpeername)
        ip_final_cliente = "127.0.0.1"
        try
            peer = Sockets.getpeername(client_socket)
            ip_final_cliente = string(peer[1]) # Extrae solo la IP del peer
        catch
        end

        # Search in headers if Nginx sent real extern IP
        for (k, v) in request.headers
            k_low = lowercase(k)
            if k_low == "x-real-ip"
                ip_final_cliente = strip(v)
                break
            elseif k_low == "x-forwarded-for"
                # X-Forwarded-For puede contener una cadena de IPs separadas por coma ("IP1, IP2").
                # La primera IP de la lista siempre es la IP original del cliente real.
                ip_final_cliente = strip(split(v, ",")[1])
                break
            end
        end

        # Actualizamos la variable local para que el log estilo Nginx de Julia muestre la IP correcta
        client_ip = ip_final_cliente

        headers_list = [(pybytes(codeunits(k)), pybytes(codeunits(v))) for (k, v) in request.headers]
        
        # Reconstruct the Nginx log string line
        request_line = "$(request.method) $(request.raw_path)$(isempty(request.query_string) ? "" : "?" * request.query_string) $(request.protocol)"

        
        # a) If the path is strictly root "/", pass it directly to the dynamic Python app
        if request.path == "/"
            # We construct the Python bytes list here, strictly in the ASGI route
            if !isnothing(python_app)
                handle_app(request, client_socket, client_ip, request_line)
                return
            else
                for file in CONFIG["index_files"]
                    if is_static_file("/$(file)")
                        if is_cgi_app("/$(file)")
                            handle_cgi(client_socket, "/$(file)", client_ip, request_line, request)
                        else
                            handle_send_file(client_socket, "/$(file)", client_ip, request_line)
                        end
                        return
                    end
                end
                if (CONFIG["allow_dirlisting"] && is_static_resource("/"))
                    handle_send_dir(client_socket, "/", client_ip, request_line)
                    return
                else    
                    send_error_response(client_socket, 404, client_ip, request_line, msg="Resource <strong>$(request.path)</strong> not found.")
                end
            end
        end

        # b) Otherwise, evaluate if it matches a local static resource path
        if is_static_resource(request.path)
            
            # b2) Is it a directory?
            if is_dir_resource(request.path)
                # b2-2) If dirlisting is allowed, handle it; else, return 403 Forbidden
                if CONFIG["allow_dirlisting"]
                    handle_send_dir(client_socket, request.path, client_ip, request_line)
                else
                    send_error_response(client_socket, 403, client_ip, request_line,
                    msg="Directory listing not allowed with current configuration.")
                end
                return
                
            else
                # b2-1) Not a directory. Is it a CGI application?
                if is_cgi_app(request.path)
                    # b2-1-2) If cgi is allowed, execute it; else, return 403 Forbidden
                    if CONFIG["allow_cgi"]
                        #handle_send_cgi(client_socket, request.path, client_ip, request_line)
                        handle_cgi(client_socket, request.path, client_ip, request_line, request)
                    else
                        send_error_response(client_socket, 403, client_ip, request_line,
                        msg="CGI handling not allowed with current configuration.")
                    end
                # ─── NUEVA ADUANA DE PHP DIRECTA ─────────────────────────────────
                elseif is_php(request.path)
                    # OxiServer catches PHP directly out of the box
                    handle_php(client_socket, request.path, client_ip, request_line, request)
                    return
                # ─── NUEVA ADUANA DE STREAMING MP4 ──────────────────────────────
                elseif is_mp_file(request.path)
                    # Gestión atómica de video con soporte HTTP 206 Range requests
                    handle_mp_streaming(client_socket, request.path, client_ip, request_line, request)
                    return
                # ─────────────────────────────────────────────────────────────────
                else
                    # b2-1-1) Not a CGI, it's a traditional static asset file
                    handle_send_file(client_socket, request.path, client_ip, request_line)
                end
                return
            end
            
        else
            # b1) Not a local static resource, delegate to the dynamic Python app (TinA/FastAPI)
            if isnothing(python_app)
                if (CONFIG["allow_dirlisting"] && is_dir_resource(request.path))
                    handle_send_dir(client_socket, request.path, client_ip, request_line)
                    return
                else    
                    send_error_response(client_socket, 404, client_ip, request_line, msg="Resource <strong>$(request.path)</strong> not found.")
                end
            else
                handle_app(request, client_socket, client_ip, request_line)
            end
            return
        end
        # =====================================================================
        
    catch e
        # Build a clean description of the error for development purposes
        error_msg = sprint(Base.showerror, e)
        
        # Log the detailed exception into stderr/error.log (English-like)
        log_msg("❌ Socket bridge exception: $error_msg", fp=stderr)
        log_msg("Stacktrace: $(sprint(Base.show_backtrace, catch_backtrace()))", fp=stderr)
        
        # 500 Log Entry style Nginx
        log_msg("$MAGENTA$(lpad(client_ip, 15))$RESET - - [$(get_styled_date())] \"$request_line\" 500 $bytes_enviados", fp=stderr)
        
        # Send the actual error description back as the HTTP response body
        try
            if isopen(client_socket)
                send_error_response(client_socket, 500, client_ip, request_line, msg="Internal Server Error (OxiServer ASGI Bridge Exception)<br><br>Details: $(error_msg)")
            end
        catch
            # Fail silently if the client already cut the connection
        end
    finally
        try close(client_socket) catch end
    end
end

function run_py_server(app::AbstractString)
    # Spawn the python worker process independently
    python_process = nothing
    try
        # 🚀 Use base_dir() to find server.py next to server.jl
        python_script_path = joinpath(base_dir(), "server.py")
        
        # 🚀 Use the Python executable from the venv if available
        python_bin = get(ENV, "OXI_PYTHON", "python3")
        
        python_process = run(pipeline(`$python_bin $python_script_path $(app) --worker`, 
                                      stdout=stdout, stderr=stderr), 
                             wait=false)
        # Give Python a brief moment to initialize and bind to the Unix Socket
        sleep(1.5)
        log_msg("Launched background ASGI handler Python process\n $(string(python_process))")
    catch exc
        log_msg("❌ Couldn't start child Python process (ASGI handler).\nERROR:\n$(exc)")
        python_process = -1
    finally
        return python_process
    end
end

"""
Inicializador global del servidor ASGI con logs y despedida unificada en el bloque finally.
"""
function run_server(app::Union{AbstractString, Nothing}; port::Int=8086, host::AbstractString="0.0.0.0")
    Base.exit_on_sigint(true)

    if !isnothing(app)
        parts = split(string(app), ":")
        if length(parts) != 2
            log_msg("❌ Formato incorrecto de aplicación. Debe ser 'modulo:aplicacion' (Ej: hello:app)", stderr)
            exit(1)
        end
        module_name = String(parts[1])
        app_name = String(parts[2])
        try
            modulo = pyimport(module_name)
            python_app = pygetattr(modulo, app_name)
            PYTHON_APP[] = python_app
        catch e
            msg1 = "❌ Server execution failed: $(sprint(Base.showerror, e))"
            msg2 = "Stacktrace: $(sprint(Base.show_backtrace, catch_backtrace()))"
            log_msg(msg1, fp=stderr)
            # Volcamos también el rastro en error.log para saber la línea exacta del fallo
            log_msg(msg2, fp=stderr)
            log_msg("Ending execution prematurely due to an error\nSee error.log for details\n", fp=stdout)
        end
    end
   
    if !isnothing(PYTHON_APP[]) 
        log_msg("[$(get_styled_date())] ℹ Initializing Python's environment...")
        run_py_server(string(app))
    else
        log_msg("[$(get_styled_date())] ℹ Starting Oxi Server in static mode...")
    end

    local server
    servidor_iniciado_con_exito = false # Bandera para el control de logs en el finally
    
    python_app = PYTHON_APP[]
    num_threads = Threads.nthreads()

    try
        # Threads.@threads for i in 1:num_threads
            # Threads.@spawn begin
        server = Sockets.TCPServer()
        Sockets.bind(server, Sockets.IPv4(host), port, reuseaddr=true, reuseport=true)
        Sockets.listen(server)
        log_msg("[$(get_styled_date())] ℹ ✔ ASGI Web Server listening at http://$host:$port (PID: $(getpid()) / Thread: $(Threads.threadid()))\n\n") 
        
        # --- Bloque de Auto-Calentamiento (Warmup) con Diagnóstico ---
        @async begin
            sleep(1.0) # Esperamos un segundo para que el servidor se estabilice antes del primer ping
            try
                # Respiro controlado para que el hilo principal se asiente en Sockets.accept
                
                # CORRECCIÓN DE SINTAXIS: Sockets.connect tradicional sin bloque 'do'
                # Forzamos la conexión local al puerto en el que está escuchando el servidor
                socket_interno = Sockets.connect(Sockets.IPv4("127.0.0.1"), port)
                
                try
                    # Enviamos una petición rústica mínima para gatillar el JIT en todo el pipeline
                    write(socket_interno, "GET /oxi_heartbeat HTTP/1.1\r\nHost: localhost\r\n\r\n")
                    flush(socket_interno)
                    
                    # Consumimos el flujo de respuesta simplemente para cerrar la comunicación
                    read(socket_interno)
                finally
                    close(socket_interno)
                end
                
            catch warmup_err
                # Si algo falla, el catch ahora nos gritará detalladamente el motivo en pantalla
                log_msg("\n[$(get_styled_date())] ⚠️ Alerta de Calentamiento: Falló la petición de precompilación:", fp=stderr)
                log_msg("$(Base.showerror(stderr, warmup_err, catch_backtrace()))\n", fp=stderr)
            end
        end
        # ---------------------------------------------------------------
        
        # Main listening loop
        while true
            local client_socket
            try
                client_socket = Sockets.accept(server) 
            catch accept_err
                # Si presionan CTRL-C o se cierra el puerto, rompemos el bucle pacíficamente
                if accept_err isa Base.IOError 
                    break
                elseif accept_err isa InterruptException
                    try
                        global_loop.stop()
                        global_loop.close()
                    catch exc
                        log_msg("⚠️ Warning: Failed to stop/close Python loop: $exc", fp=stderr)
                    end
                    break
                else
                    rethrow(accept_err)
                end
            end
            
            @async handle_conn(client_socket, python_app)
                # end
            # end
        end
        servidor_iniciado_con_exito = true
    catch e
        # El catch principal ahora solo se preocupa por reportar fallas reales no controladas
        if !(e isa InterruptException)
            log_msg("❌ Server execution failed: $(sprint(Base.showerror, e))", fp=stderr)
            # Volcamos también el rastro en error.log para saber la línea exacta del fallo
            log_msg("Stacktrace: $(sprint(Base.show_backtrace, catch_backtrace()))", fp=stderr)
            log_msg("❌ Server execution failed: $(sprint(Base.showerror, e))", fp=stdout)
            # Volcamos también el rastro en error.log para saber la línea exacta del fallo
            log_msg("Stacktrace: $(sprint(Base.show_backtrace, catch_backtrace()))", fp=stdout)
        else
            try
                global_loop.stop()
                global_loop.close()
            catch exc
                log_msg("⚠️ Warning: Failed to stop/close Python loop: $exc", fp=stderr)
            end
            log_msg("[$(get_styled_date())] ℹ Servidor ASGI detenido por señal de interrupción (CTRL-C).", fp=stdout)
        end
    finally
        # TU PROPUESTA: Centralización absoluta del apagado amable en el finally
        if servidor_iniciado_con_exito
            log_msg("\n[$(get_styled_date())] ℹ Servidor ASGI cerrándose amablemente... ¡Hasta luego!", fp=stdout)
        end

        # Garantizar la liberación inmediata del puerto del sistema operativo
        if @isdefined(server                                                           ) && isopen(server                                                           )
            close(server                                                           )
        end

        # SOLUCIÓN CRÍTICA: Forzamos la salida limpia del proceso al sistema operativo.
        # Esto impide que las micro-tareas huérfanas del scheduler de Julia lancen fallas fatales en el hook de cierre.
        if servidor_iniciado_con_exito
            exit(0)
        end
    end
end

function run_server(; port::Int=8086, host::AbstractString="0.0.0.0")
    run_server(nothing, port=port, host=host)
end

# =============================================================================================
function clearscreen() 
    try
        if Sys.iswindows()
            run(`cmd /c cls`)
        else
            run(`clear`)
        end
    catch
    end
end

function julia_main()::Cint
    if !isdir("$(current_dir())/logs")
        mkpath("$(current_dir())/logs")
    end
    err_fp::IOStream = open("$(current_dir())/logs/error.log", "w")
    redirect_stderr(err_fp)

    argslen = length(ARGS)

    app_param::String = ""
    port_param::Int = 8086

    clearscreen()

    if argslen == 0 
        try
            run_server(port=port_param)
        catch exc
            println("❌ Server(port=$(port_param)) couldn't run\n\nException:\n$(exc)")
        finally
            return 0
        end
    elseif argslen == 1
        if isdigit(ARGS[begin])
            try
                port_param = parse(Int, ARGS[begin])
                run_server(port=port_param)                 
            catch exc
                println("❌ Server(port=$(port_param)) couldn't run\n\nException:\n$(exc)")
            finally
                return 0
            end
        else
            try
                run_server(ARGS[begin], port=port_param)
            catch exc
                println("❌ Server(app_target=$(ARGS[begin])) couldn't run\n\nException:\n$(exc)")
            finally
                return 0
            end
        end
    elseif argslen == 2
        if isdigit(ARGS[begin])
            print("❌ Parameter error: first parameter must be the app, not the port\n")
            return 1
        else
            if isdigit(ARGS[end])
                try
                    port = parse(Int, ARGS[end])
                    run_server(ARGS[begin], port=port)
                catch exc
                    println("❌ Server(app_target=$(ARGS[begin]), port=$(port)) couldn't run\n\nException:\n$(exc)")
                finally
                    return 0
                end
            else
                println("❌ Server couldn't run\n\nSecond parameter must be a digit for the chosen port.")
                return 0
            end
        end
    else
        try
            run_server(ARGS[begin], port=parse(Int, ARGS[end - 1]), host=ARGS[end])
        catch exc
            println("❌ Server couldn't run\n\nException:\n$(exc)")
        finally
            return 0
        end
    end

    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    julia_main()
end

# ==============================================================================================

end # Package ends here
