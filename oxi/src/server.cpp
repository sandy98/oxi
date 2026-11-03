#include "server.hpp"

extern char** environ; // Acceso al entorno global del sistema

int signal_pipe[2] = {-1, -1};
std::atomic<bool> shutdown_requested(false);

std::atomic<int> active_connections{0};
std::mutex shutdown_mutex;
std::condition_variable shutdown_cv;

int server_fd = -1;
std::atomic<bool> server_running(true);
std::atomic<bool> lifespan_fatal_error(false);

std::thread python_loop_thread;
std::thread loop_thread;

PyObject* py_loop_object = nullptr; 
PyObject* py_run_from_socket_func = nullptr; 
PyObject* py_asgi_app_object = nullptr;      // Defaults to nullptr

// Global variable tracking if an app target was successfully provided via CLI
std::string app_target_string = "";
bool has_application_target = false;

std::string PHP_BINARY_PATH("");

std::unordered_map<std::string, std::string> cgi_handlers;

// Persistent global configurations cached from Python
std::string VERSION;
PyObject* py_server_version = nullptr;

using ConfigValue = std::variant<std::string, bool, long>;
struct string_hash {
    using is_transparent = void; // Enables heterogeneous lookup capability

    size_t operator()(const char* txt) const {
        return std::hash<std::string_view>{}(txt);
    }
    size_t operator()(std::string_view txt) const {
        return std::hash<std::string_view>{}(txt);
    }
    size_t operator()(const std::string& txt) const {
        return std::hash<std::string>{}(txt);
    }
};

std::unordered_map<std::string, ConfigValue, string_hash, std::equal_to<>> CONFIG;

std::string CGI_DIR;
std::string STATIC_DIR;
// std::string CGI_ANCHOR;

PyObject* py_server_config = nullptr; 

// PyObject* py_send_error_func = nullptr; // Global cached HTML error renderer
// PyObject* py_send_dir_func = nullptr; // Global cached HTML directory lister

std::atomic<bool> python_ready(false);
std::atomic<bool> uvloop_available(false);

std::vector<std::string> cached_index_files;

#ifdef _WIN32
    constexpr char PATH_SEP = ';';
    const std::vector<std::string> EXEC_EXTS {".exe", ".bat", ".cmd", ""};
#else
    constexpr char PATH_SEP = ':';
    const std::vector<std::string> EXEC_EXTS = {""};
#endif

// std::osyncstream synced_out(std::cout);

#define synced_out std::cout

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Functions
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

std::filesystem::path get_executable_directory() {
#if defined(_WIN32)
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    return std::filesystem::path(path).parent_path();

#elif defined(__linux__)
    char path[PATH_MAX];
    ssize_t count = readlink("/proc/self/exe", path, PATH_MAX);
    if (count != -1) {
        path[count] = '\0';
        return std::filesystem::path(path).parent_path();
    }
#endif

    return ""; // Fallback
}


void clear_screen() {
    std::cout << "\033[2J\033[1;1H" << std::flush;
}

/// Try to find in the Haystack the Needle - ignore case
auto findStringIC(const std::string& strHaystack, const std::string& strNeedle) {
  auto it = std::search(
    strHaystack.begin(), strHaystack.end(),
    strNeedle.begin(),   strNeedle.end(),
    [](unsigned char ch1, unsigned char ch2) { return std::toupper(ch1) == std::toupper(ch2); }
  );
  return it;
}

bool bFindStringIC(const std::string& strHaystack, const std::string& strNeedle) {
    auto it = findStringIC(strHaystack, strNeedle);
    return (it != strHaystack.end() );
}

bool isHtml(const std::string fragment) {
    return bFindStringIC(fragment, "<!DOCTYPE html") || bFindStringIC(fragment, "<html") || bFindStringIC(fragment, "<head")
     || bFindStringIC(fragment, "<body") || bFindStringIC(fragment, "<div") || bFindStringIC(fragment, "<p") || bFindStringIC(fragment, "<br")
     || bFindStringIC(fragment, "<hr") || bFindStringIC(fragment, "<style") || bFindStringIC(fragment, "<h1")
     || bFindStringIC(fragment, "<h2") || bFindStringIC(fragment, "<h3") || bFindStringIC(fragment, "<h4") || bFindStringIC(fragment, "<h5")
     || bFindStringIC(fragment, "<h6") || bFindStringIC(fragment, "<pre") || bFindStringIC(fragment, "<a") || bFindStringIC(fragment, "<ul");
}

bool has_content_type(const std::string fragment) {
    return bFindStringIC(fragment, "content-type");
}

bool has_content_length(const std::string fragment) {
    return bFindStringIC(fragment, "content-length");
}

std::string pad_left(const std::string& s, size_t width = 15, char fill = ' ') {
    std::ostringstream oss;
    oss << std::setfill(fill) << std::setw(static_cast<int>(width)) << s;
    return oss.str();
}

std::mutex log_mutex;

template <typename... Args>
void log_msg(Args&&... args) {
    std::ostringstream oss;
    (oss << ... << std::forward<Args>(args));   // C++17 fold expression
    // synced_out << oss.str() << '\n';
    // synced_out.emit();
    oss << '\n';
    std::lock_guard<std::mutex> lock(log_mutex);
    std::cout << oss.str(); // std::cout is line-buffered, this triggers a write() on newline
}

std::string get_styled_date() {
    std::time_t now = std::time(nullptr);
    std::tm* local_time = std::localtime(&now);

    char buffer[100];
    // %d: día, %b: mes abreviado, %Y: año 4 dígitos, %H:%M:%S: hora, %z: zona horaria
    std::strftime(buffer, sizeof(buffer), "%d %b %Y %H:%M:%S %z", local_time);

    return std::string(buffer);
}

void log_access(const Request& request, int status_code, int bytes_sent) {
    std::string remote_addr = request.get_client_ip();
    std::string request_line = request.get_request_line();
    std::ostringstream nginx_log_line;
    nginx_log_line << GREEN << pad_left(remote_addr) << RESET << " - - [" << get_styled_date() << "] " << request_line << " " << status_code  << " " << bytes_sent;
    log_msg(nginx_log_line.str());
}

static bool write_all(int fd, const char* p, size_t n) {
    while (n > 0) {
        ssize_t w = send(fd, p, n, 0); // MSG_NOSIGNAL is an alternative on Linux
        if (w < 0) {
            if (errno == EINTR) continue;
            return false; // EPIPE, ECONNRESET, etc.
        }
        if (w == 0) return false;
        p += w;
        n -= static_cast<size_t>(w);
    }
    return true;
}

// Non destructive capture of HTTP request's first line. 
std::string peek_request_line(int client_fd) {
    char peek_buffer[1024]; 
    ssize_t received = recv(client_fd, peek_buffer, sizeof(peek_buffer) - 1, MSG_PEEK);
    if (received <= 0) return "";
    
    peek_buffer[received] = '\0';
    std::string raw_string(peek_buffer);
    
    // Find the end of the first line
    size_t eol_pos = raw_string.find("\r\n");
    if (eol_pos == std::string::npos) {
        // If there's no CRLF in the first 1024 bytes, it's either a malformed 
        // request or a giant URL. Let the main parser handle the error.
        return ""; 
    }
    
    std::string request_line = raw_string.substr(0, eol_pos);
    
    // 🚀 Only check the request line for path traversal
    if (request_line.find("..") != std::string::npos) {
        return ""; // Will trigger a 400 Bad Request in handle_client
    }
    
    return request_line; 
}

std::string get_mime_type(const std::string& filepath) {
    size_t dot_pos = filepath.find_last_of('.');
    if (dot_pos == std::string::npos) return "application/octet-stream";
    
    std::string ext = filepath.substr(dot_pos);
    std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
    
    if (ext == ".html" || ext == ".htm") return "text/html; charset=utf-8";
    if (ext == ".txt") return "text/plain; charset=utf-8";
    if (ext == ".css") return "text/css; charset=utf-8";
    if (ext == ".js")  return "application/javascript; charset=utf-8";
    if (ext == ".jpeg" || ext == ".jpg") return "image/jpeg";
    if (ext == ".png")  return "image/png";
    if (ext == ".gif")  return "image/gif";
    if (ext == ".ico")  return "image/x-icon";
    if (ext == ".mp4")  return "video/mp4";
    if (ext == ".mp3")  return "audio/mpeg";
    if (ext == ".json") return "application/json; charset=utf-8";
    
    return "application/octet-stream";
}

std::string which(const std::string& program) {
    namespace fs = std::filesystem;

    // If the program already contains a path separator, check it directly.
    if (program.find('/') != std::string::npos
#ifdef _WIN32
        || program.find('\\') != std::string::npos
#endif
    ) {
        if (fs::exists(program)) return fs::absolute(program).string();
        return "";
    }

    const char* path_env = std::getenv("PATH");
    if (!path_env) return "";

    std::string path_str(path_env);
    size_t start = 0;

    while (start <= path_str.size()) {
        size_t end = path_str.find(PATH_SEP, start);
        if (end == std::string::npos) end = path_str.size();

        std::string dir = path_str.substr(start, end - start);
        if (!dir.empty()) {
            for (const auto& ext : EXEC_EXTS) {
                fs::path candidate = fs::path(dir) / (program + ext);
                std::error_code ec;
                if (fs::exists(candidate, ec) && !ec) {
                    // On POSIX, ensure it's actually executable.
#ifndef _WIN32
                    auto perms = fs::status(candidate, ec).permissions();
                    if (ec || (perms & fs::perms::owner_exec) == fs::perms::none)
                        continue;
#endif
                    return fs::absolute(candidate).string();
                }
            }
        }

        if (end == path_str.size()) break;
        start = end + 1;
    }

    return ""; // not found
}

void probe_php_runtime() {
    std::string cgi_path = which("php-cgi");
    if (!cgi_path.empty()) {
        PHP_BINARY_PATH = cgi_path;
        return;
    }
    cgi_path = which("php");
    if (!cgi_path.empty()) {
        PHP_BINARY_PATH = cgi_path;
    }
}

// 2. The template can now take anything string-like cleanly
template <typename T>
T get_config(std::string_view key, T default_val = T{}) {
    auto it = CONFIG.find(key); // No allocation occurs, even if passed a const char*
    if (it != CONFIG.end()) {
        if (const auto* ptr = std::get_if<T>(&it->second)) {
            return *ptr;
        }
    }
    return default_val;
}

// Helper to extract a string from CONFIG
std::string get_config_string(const std::string& key, const std::string& default_val = "") {
    return get_config<std::string>(key, default_val);
}

// Helper to extract a bool from CONFIG
bool get_config_bool(const std::string& key, bool default_val = true) {
    return get_config<bool>(key, default_val);
}

// 🚀 NUEVO: Wrapper explícito para enteros largos
long get_config_long(const std::string& key, long default_val = 0) {
    return get_config<long>(key, default_val);
}

void probe_cgi_handlers() {
    cgi_handlers[".py"] = which("python3");
    cgi_handlers[".pl"] = which("perl");
    cgi_handlers[".php"] = PHP_BINARY_PATH;
    cgi_handlers[".java"] = which("java");
    cgi_handlers[".rb"] = which("ruby");
    cgi_handlers[".sh"] = which("bash");
}

extern "C" void set_lifespan_fatal() {
    Py_BEGIN_ALLOW_THREADS
    const char* msg = "\n\034[31m[Server]\033[0m Aborting server startup due to Lifespan failure.\n";
    (void)write(STDOUT_FILENO, msg, strlen(msg));
    _exit(2);
    Py_END_ALLOW_THREADS
    
    // lifespan_fatal_error = true;
}

void init_python_objs() {
    CwdGuard* cwd_guard = new CwdGuard(); // Ensure CWD is restored on scope exit;
    std::filesystem::path exe_dir = get_executable_directory();
    std::filesystem::current_path(exe_dir); // Change CWD to the executable's directory
    
    log_msg(CYAN, "[Python Worker]", RESET, " Initializing global asyncio loop...");
    
    PyGILState_STATE gstate = PyGILState_Ensure();

    PyRun_SimpleString(
        "import asyncio\n"
        "import sys\n"
        "sys.path.append('.')\n"
        "import server\n" 
        "global_loop = asyncio.new_event_loop()\n"
        "asyncio.set_event_loop(global_loop)\n"
        "server._embedded_global_loop = global_loop\n" 
        "print('\033[36m[Python Worker]\033[0m Global asyncio loop instantiated and linked successfully.')\n"
    );

    PyObject* main_module = PyImport_AddModule("__main__");
    PyObject* main_dict = PyModule_GetDict(main_module);
    py_loop_object = PyDict_GetItemString(main_dict, "global_loop");
    Py_XINCREF(py_loop_object); 
    PyObject* pServerModule = PyImport_ImportModule("server");

    if (pServerModule != nullptr) {
        PyObject* py_uvloop_available = PyObject_GetAttrString(pServerModule, "uvloop_available");
        if (py_uvloop_available && PyBool_Check(py_uvloop_available)) {
            int truth_value = PyObject_IsTrue(py_uvloop_available);
            if (truth_value == -1) {
                log_msg(RED, "[Python Worker]", RESET, " Error reading Uvloop availability.");
            } else {
                if (truth_value == 1) {
                uvloop_available = true;
                log_msg(CYAN, "[Python Worker]", RESET, " Asyncio using Uvloop."); 
                } else {
                    log_msg(CYAN, "[Python Worker]", RESET, " Uvloop module not available. Asyncio using built-in loop.");
                }
            }
        } else {
            log_msg(CYAN, "[Python Worker]", RESET, " Uvloop module not available. Asyncio using built-in loop.");
        }

        py_run_from_socket_func = PyObject_GetAttrString(pServerModule, "run_from_socket");
        if (py_run_from_socket_func && PyCallable_Check(py_run_from_socket_func)) {
            log_msg(CYAN, "[Python Worker]", RESET, " Server ASGI/WSGI handler cached successfully.");
        }

        py_server_config = PyObject_GetAttrString(pServerModule, "CONFIG");
        if (py_server_config && PyDict_Check(py_server_config)) {
            PyObject* pIndexFilesList = PyDict_GetItemString(py_server_config, "index_files");
            if (pIndexFilesList && PyList_Check(pIndexFilesList)) {
                Py_ssize_t size = PyList_Size(pIndexFilesList);
                std::cout << CYAN << "[Python Worker]" << RESET " Caching index files: ";
                for (Py_ssize_t i = 0; i < size; ++i) {
                    PyObject* pItem = PyList_GetItem(pIndexFilesList, i);
                    if (pItem && PyUnicode_Check(pItem)) {
                        std::string index_file = PyUnicode_AsUTF8(pItem);
                        cached_index_files.push_back(index_file);
                        std::cout << index_file << " ";
                    }
                }
                std::cout << " in C++ vector." << std::endl << std::flush;
            }

            PyObject* key;
            PyObject* value;
            Py_ssize_t pos = 0;
            while (PyDict_Next(py_server_config, &pos, &key, &value)) {
                std::string key_str;
                if (PyUnicode_Check(key)) {
                    key_str = PyUnicode_AsUTF8(key);
                } else {
                    continue;
                }

                if (PyBool_Check(value)) {
                    CONFIG[key_str] = (value == Py_True);
                } else if (PyLong_Check(value)) {
                    CONFIG[key_str] = PyLong_AsLong(value);
                } else if (PyUnicode_Check(value)) {
                    CONFIG[key_str] = PyUnicode_AsUTF8(value);
                }
            } 
            
            log_msg(CYAN, "[Python Worker]", RESET, " Server global CONFIG successfully cached in C++.");

            // 🚀 BUILD THE CGI ANCHOR
            STATIC_DIR = get_config_string("static_dir", "static");
            CGI_DIR    = get_config_string("cgi_dir",    "cgi-bin");
            // CGI_ANCHOR = STATIC_DIR + "/" + CGI_DIR + "/";
            log_msg(CYAN, "[Python Worker]", RESET, " Static directory: '", STATIC_DIR, "'   /   CGI directory: '", CGI_DIR, "'");            
        }

        py_server_version = PyObject_GetAttrString(pServerModule, "VERSION");
        if (py_server_version) {
            Py_ssize_t size = 0;
            VERSION = PyUnicode_AsUTF8AndSize(py_server_version, &size);
            log_msg(CYAN, "[Python Worker]", RESET, " Server global VERSION successfully cached in C++: ", VERSION);
        }

//      std::filesystem::current_path(cwd_guard.original_path); // Restore CWD after Python initialization
        delete cwd_guard; // Explicitly delete to restore CWD before proceeding

        if (has_application_target) {
            log_msg(CYAN, "[Python Worker]", RESET, " Preloading application target: ", app_target_string,  "...");
            PyObject* pLoadFunc = PyObject_GetAttrString(pServerModule, "load_application_target");
            if (pLoadFunc && PyCallable_Check(pLoadFunc)) {
                PyObject* pTargetStrPy = PyUnicode_FromString(app_target_string.c_str());
                PyObject* pArgs = PyTuple_New(1);
                PyTuple_SetItem(pArgs, 0, pTargetStrPy); 
                py_asgi_app_object = PyObject_CallObject(pLoadFunc, pArgs);
                Py_DECREF(pArgs);
                Py_DECREF(pLoadFunc);
            }

            if (py_asgi_app_object != nullptr) {
                PyObject* pServerMod = PyImport_ImportModule("server");
                if (pServerMod) {
                    PyObject_SetAttrString(pServerMod, "py_asgi_app_object", py_asgi_app_object);
                    Py_DECREF(pServerMod);
                    log_msg(GREEN, "[C++]", RESET, " CWD: ", std::filesystem::current_path().string());
                }

                // 🚀 START THE LOOP IN A JOINABLE THREAD
                loop_thread = std::thread([]() {
                    PyGILState_STATE loop_gstate = PyGILState_Ensure();
                    PyRun_SimpleString("global_loop.run_forever()");
                    PyGILState_Release(loop_gstate);
                });

                // Queue the lifespan startup
                PyRun_SimpleString(
                    "import asyncio\n"
                    "import server\n"
                    "async def _start_lifespan():\n"
                    "    try:\n"
                    "        server._lifespan_q, server._lifespan_ev, server._lifespan_task = await server.run_lifespan(server.py_asgi_app_object, server._embedded_global_loop)\n"
                    "    except Exception as e:\n"
                    "        print(f'\\033[31m[Lifespan] Fatal startup error: {e}\\033[0m', flush=True)\n"
                    "        import os; os._exit(1)\n"
                    "asyncio.run_coroutine_threadsafe(_start_lifespan(), server._embedded_global_loop)\n"
                );

                // 🚀 RELEASE THE GIL SO THE LOOP THREAD CAN RUN
                PyGILState_Release(gstate); 

                // Poll for lifespan completion
                bool startup_done = false;
                while (!startup_done) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(50));
                    
                    PyGILState_STATE poll_gstate = PyGILState_Ensure();
                    PyObject* pReady = PyObject_GetAttrString(pServerModule, "_lifespan_ready");
                    if (pReady && PyObject_IsTrue(pReady)) {
                        startup_done = true;
                    }
                    Py_XDECREF(pReady);
                    PyGILState_Release(poll_gstate);
                }
                
                // 🚀 RE-ACQUIRE THE GIL TO CONTINUE
                gstate = PyGILState_Ensure();
            }
        } else {
            log_msg(CYAN, "[Python Worker]", RESET, " No application target provided. Standing by in static/error fallback mode.");
        }
        Py_DECREF(pServerModule);
    } else {
        PyErr_Print();
        std::cerr << "CRITICAL: Could not import 'server.py'" << std::endl;
    }

    log_msg(CYAN, "[Python Worker]", RESET, " Server core hooks cached.", '\n', '\n', 
        "================================================================================", '\n', '\n');
    
    python_ready = true;     
    PyGILState_Release(gstate); // Release the GIL we re-acquired after polling

    // 🚀 WAIT FOR THE LOOP THREAD TO FINISH
    // This keeps python_loop_thread alive and prevents the PyGILState crash
    if (loop_thread.joinable()) {
        loop_thread.join();
    }
}

void split_string(const std::string& path, std::vector<std::string>& split_path, const char sep = '/') {
    split_path.clear();
    size_t start = 0;
    size_t end = path.find(sep);
    
    while (end != std::string::npos) {
        if (end > start) {
            split_path.emplace_back(path.substr(start, end - start));
        }
        start = end + 1;
        end = path.find(sep, start);
    }
    
    // Don't forget the last segment
    if (start < path.length()) {
        split_path.emplace_back(path.substr(start));
    }
}

// bool is_cgi(const std::string& local_path) {
//     // Split the path and look for the cgi directory
//     std::vector<std::string> segments;
//     split_string(local_path, segments);
    
//     for (const auto& segment : segments) {
//         // if (segment == cgi_dir) {
//         if (segment == CGI_DIR) {
//             return true;
//         }
//     }
    
//     return false;
// }

// 🚀 Intent: Is this path inside a protected CGI directory?
bool in_cgi_dir(const std::string& local_path) {
    std::vector<std::string> segments;
    split_string(local_path, segments);
    for (const auto& segment : segments) {
        if (segment == CGI_DIR) return true;
    }
    return false;
}

// 🚀 Intent: Should this specific file be executed as a CGI script?
bool is_cgi_script(const std::string& local_path) {
    // 1. It must be inside the static dir (prevents executing arbitrary system files)
    if (local_path.rfind(STATIC_DIR, 0) != 0) return false;
    
    // 2. It must be inside a CGI directory
    return in_cgi_dir(local_path);
}

bool is_php(const std::string& web_path) {
    size_t dot_pos = web_path.find_last_of('.');
    return dot_pos != std::string::npos && (web_path.substr(dot_pos) == ".php" || web_path.substr(dot_pos) == ".php3");
}

int is_static(const std::string& web_path, std::string& out_local_path) {
    std::string static_dir = get_config_string("static_dir", "static");
    bool allow_dirlisting = get_config_bool("allow_dirlisting", true);
    bool allow_cgi = get_config_bool("allow_cgi", true);

    // 1. Clonar la ruta para no alterar el argumento original
    std::string path_copy = web_path;

    // 🚀 REGLA DE ORO DE PRECEDENCIA DE LA RAÍZ:
    // Si se solicita la raíz ("/" o vacía) y SÍ tenemos una app ASGI activa en C++,
    // ignoramos el disco por completo y forzamos el desvío directo a Python.
    if ((path_copy == "/" || path_copy.empty()) && has_application_target && py_asgi_app_object != nullptr) {
        return 404; // Esto obligará a handle_client a irse por la rama offload_to_python_asgi
    }

    
    // 2. Si está vacía o es un solo caracter, la tratamos de forma directa
    if (path_copy.empty() || path_copy == "/") {
        out_local_path = static_dir;
    } else {
        size_t start = (path_copy[0] == '/') ? 1 : 0;
        size_t end = path_copy.length();
        
        // Si tiene un trailing slash al final, acortamos el límite de lectura
        if (end > 1 && path_copy[end - 1] == '/') {
            end--;
        }
        
        // Extraemos de un solo golpe la ruta limpia y normalizada sin alterar la memoria
        std::string clean_path = path_copy.substr(start, end - start);
        out_local_path = static_dir + "/" + clean_path;
    }

    // ... (after out_local_path is assigned) ...
    
    // 🚀 PATH CONTAINMENT CHECK
    namespace fs = std::filesystem;
    std::error_code ec;
    fs::path root_abs = fs::weakly_canonical(fs::absolute(static_dir, ec), ec);
    if (ec) return 404;

    fs::path target_abs = fs::weakly_canonical(fs::absolute(out_local_path, ec), ec);
    if (ec) return 404;

    std::string root_str = root_abs.string();
    std::string target_str = target_abs.string();
    
    // Ensure target is root OR starts with "root/" (to prevent "staticfoo" matching "static")
    bool is_inside = (target_str == root_str) || 
                     (target_str.size() > root_str.size() &&
                      target_str.compare(0, root_str.size(), root_str) == 0 &&
                      target_str[root_str.size()] == '/');

    if (!is_inside) {
        log_msg(RED, "[C++ FastPath]", RESET, " Path escapes document root: ", out_local_path);
        return 403; // Or 404
    }


    // 3. Inspección física en disco (Airtight checkpoint)
    struct stat path_stat;
    if (stat(out_local_path.c_str(), &path_stat) != 0) {
        // 🚀 PATH_INFO fallback: try splitting the path at each '/' from the end,
        // looking for a file that exists (usually a CGI script).
        std::string split_path = out_local_path;
        size_t slash = split_path.find_last_of('/');
        
        while (slash != std::string::npos && slash > 0) {
            split_path = split_path.substr(0, slash);
            if (stat(split_path.c_str(), &path_stat) == 0 && S_ISREG(path_stat.st_mode)) {
                // Found a regular file; the rest is PATH_INFO.
                // Only treat it as CGI if it lives in the CGI anchor.
                #ifndef __NDEBUG__
                    log_msg(YELLOW, "[DEBUG]", RESET, " PATH_INFO split: ", out_local_path);
                #endif               
                if (is_cgi_script(split_path)) {
                    out_local_path = split_path; // Return the script path
                    return 200; // Routing will handle it as CGI
                }
                break; // Found a file, but not CGI → give up
            }
            slash = split_path.find_last_of('/');
        }
        
        // Nothing matched; fall through to 404
        return 404;
    }

    if (S_ISREG(path_stat.st_mode)) {
        if (is_cgi_script(out_local_path)) { // Pasamos la ruta completa calculada para validar cgi-bin
            if (allow_cgi) {
                // log_msg(RED, "[C++ FastPath]", RESET, " Will return cgi content: ", out_local_path);
                return 200; 
            } else {
                log_msg(RED, "[C++ FastPath]", RESET, " CGI execution is forbidden: ", out_local_path);
                return 403; 
            }
        } else {
            // log_msg(RED, "[C++ FastPath]", RESET, " Will return static file: ", out_local_path);
            return 200; 
        }
    }

    if (S_ISDIR(path_stat.st_mode)) {
        if (static_cast<bool>(allow_dirlisting) && !in_cgi_dir(out_local_path)) {
            // log_msg(RED, "[C++ FastPath]", RESET, " Directory listing will be sent for: ", out_local_path);
            return 200; 
        } else {
            log_msg(RED, "[C++ FastPath]", RESET, " CGI directory listing is forbidden: ", out_local_path);
            return 403; 
        }
    }

    return 404;
}

void send_error_html(int client_fd, const Request& request, int status_code, const std::string& msg) {
    // 1. Determine status phrase
    std::string status_phrase;
    switch (status_code) {
            case 200: status_phrase = "OK"; break;
            case 201: status_phrase = "Created"; break;
            case 204: status_phrase = "No Content"; break;
            case 301: status_phrase = "Moved Permanently"; break;
            case 302: status_phrase = "Found"; break;
            case 304: status_phrase = "Not Modified"; break;
            case 400: status_phrase = "Bad Request"; break;
            case 401: status_phrase = "Unauthorized"; break;
            case 403: status_phrase = "Forbidden"; break;
            case 404: status_phrase = "Not Found"; break;
            case 405: status_phrase = "Method Not Allowed"; break;
            case 413: status_phrase = "Payload Too Large"; break;
            case 414: status_phrase = "URI Too Long"; break;
            case 429: status_phrase = "Too Many Requests"; break;
            case 500: status_phrase = "Internal Server Error"; break;
            case 501: status_phrase = "Not Implemented"; break;
            case 502: status_phrase = "Bad Gateway"; break;
            case 503: status_phrase = "Service Unavailable"; break;
            case 504: status_phrase = "Gateway Timeout"; break;
            default:  status_phrase = "Error"; break;
    }

    // 2. Extract telemetry from request
    std::string method = request.get_method();
    std::string path   = request.get_path();
    std::string client_ip = request.get_client_ip();
    std::string protocol = request.get_protocol();
    std::string request_line = method + " " + path + " " + protocol;

    // 3. Build HTML body
    std::string body = "<!DOCTYPE html>\n<html>\n<head>"
                       "<title>" + std::to_string(status_code) + " " + status_phrase + "</title>"
                       "<style>body { font-family: monospace; margin: 3rem; background: #fafafa; }</style>"
                       "</head>\n<body>\n"
                       "<h1>" + std::to_string(status_code) + " " + status_phrase + "</h1>"
                       "<p>" + msg + "</p>"
                       "<div><b>Client IP:</b> " + client_ip + "<br>"
                       "<b>Request:</b> " + request_line + "</div>\n"
                       "<hr><small>OxiServer/" + VERSION + " (C++ Powered)</small>\n"
                       "</body>\n</html>";

    // 4. Build headers
    std::string headers = "HTTP/1.1 " + std::to_string(status_code) + " " + status_phrase + "\r\n"
                          "Date: " + get_rfc_date() + "\r\n"
                          "Server: OxiServer/" + VERSION + "\r\n"
                          "Content-Type: text/html; charset=utf-8\r\n"
                          "Content-Length: " + std::to_string(body.length()) + "\r\n"
                          "Connection: close\r\n\r\n";

    // 5. Transmit
    size_t bytes_sent = headers.length() + body.length();
    if (!write_all(client_fd, headers.c_str(), headers.length())) {
        shutdown(client_fd, SHUT_RDWR);
        close(client_fd);
        return;
    }
    if (!write_all(client_fd, body.c_str(), body.length())) {
        shutdown(client_fd, SHUT_RDWR);
        close(client_fd);
        return;
    }
    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);

    // 6. Log the access
    log_access(request, status_code, bytes_sent);
}

void send_error(int client_fd, int status_code, const char* msg, const Request& request) {
    send_error_html(client_fd, request, status_code, msg);
}

void handle_static(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path) {
    // const_cast<Request&>(request).consume_headers();
    struct stat path_stat;
    
    if (stat(local_path.c_str(), &path_stat) != 0) {
        std::string message = "Not Found (Static/CGI Path Missing): " + web_path;
        // Pasamos el objeto request directo
        send_error(client_fd, 404, message.c_str(), request);
        return;
    }

    std::string target_path = local_path;

    if (S_ISDIR(path_stat.st_mode)) {
        bool index_found = false;
        for (const auto& index_file : cached_index_files) {
            std::string possible_index = target_path + "/" + index_file;
            struct stat index_stat;
            if (stat(possible_index.c_str(), &index_stat) == 0 && S_ISREG(index_stat.st_mode)) {
                log_msg(GREEN, "[C++ FastPath]", RESET, " Directory mapped to index file: ", possible_index);
                target_path = possible_index;
                path_stat = index_stat;
                index_found = true;
                break;
            }
        }

        if (!index_found) {
            if (in_cgi_dir(target_path)) {
                // 🚀 Block CGI directory listings before doing any heavy lifting
                send_error_html(client_fd, request, 403, "Forbidden (CGI Directory Access Denied)");
                return;
            }
            // 🚀 Use the new C++ renderer
            handle_send_dir_cpp(client_fd, request, target_path, web_path);
            return;
        } else {
            log_msg(GREEN, "[C++ FastPath]", RESET, " FastPath] Index file found in requested directory will be sent for: ", web_path);
            // Al encontrar un index_file, re-evaluamos el target_path como archivo regular
        }
    }

    if (S_ISREG(path_stat.st_mode)) {
        if (is_cgi_script(target_path) || is_php(target_path)) {
            handle_cgi(client_fd, request, target_path, web_path);
            return;
        }
        
        handle_sendfile(client_fd, request, target_path, web_path);
        return;
    }

    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);
}

std::string get_rfc_date() {
    std::time_t now = std::time(nullptr);
    std::tm* gmt = std::gmtime(&now);
    
    // Format: "Tue, 27 Oct 2026 14:00:22 GMT"
    char buffer[64];
    std::strftime(buffer, sizeof(buffer), "%a, %d %b %Y %H:%M:%S GMT", gmt);
    return std::string(buffer);
}

void handle_sendfile(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path) {
    struct stat path_stat;
    if (stat(local_path.c_str(), &path_stat) != 0) {
        std::string message = "Not Found: " + web_path;
        send_error(client_fd, 404, message.c_str(), request);
        return;
    }

    std::string mime_type = get_mime_type(local_path);
    size_t total_file_size = path_stat.st_size;

    // Abrir el archivo en bajo nivel (POSIX) para obtener su descriptor de entrada
    int file_fd = open(local_path.c_str(), O_RDONLY);
    if (file_fd < 0) {
        std::string msg = "Internal Server Error (Could not read local file '" + web_path + "')";
        send_error(client_fd, 500, msg.c_str(), request);
        return;
    }

    off_t offset_start = 0;
    size_t bytes_to_send = total_file_size;
    int status_code = 200;
    std::string status_phrase = "OK";
    std::string extra_headers = "";

    // INTEGRAR NATIVE HTTP 206 RANGE MATCHING via Request object
    if (request.has_header("range")) {
        std::string range_val = request.get_header("range");
        if (range_val.rfind("bytes=", 0) == 0) {
            std::string range_bytes = range_val.substr(6);
            size_t dash_pos = range_bytes.find('-');
            
            if (dash_pos != std::string::npos) {
                try {
                    std::string start_str = range_bytes.substr(0, dash_pos);
                    std::string end_str = range_bytes.substr(dash_pos + 1);

                    if (!start_str.empty()) {
                        offset_start = std::stoll(start_str);
                    }
                    
                    off_t offset_end = total_file_size - 1;
                    if (!end_str.empty()) {
                        offset_end = std::stoll(end_str);
                    }

                    // Enforce structural boundary safeguards
                    offset_start = std::max(static_cast<off_t>(0), std::min(offset_start, static_cast<off_t>(total_file_size - 1)));
                    offset_end = std::max(offset_start, std::min(offset_end, static_cast<off_t>(total_file_size - 1)));

                    bytes_to_send = offset_end - offset_start + 1;
                    status_code = 206;
                    status_phrase = "Partial Content";
                    
                    extra_headers = "Content-Range: bytes " + std::to_string(offset_start) + "-" + 
                                    std::to_string(offset_end) + "/" + std::to_string(total_file_size) + "\r\n";
                } catch (...) {
                    offset_start = 0;
                    bytes_to_send = total_file_size;
                    status_code = 200;
                    status_phrase = "OK";
                }
            }
        }
    }

    // Emit official compliance HTTP response headers
    std::ostringstream sn;
    sn << "OxiServer/" << VERSION << "";

    std::string headers = 
        "HTTP/1.1 " + std::to_string(status_code) + " " + status_phrase + "\r\n"
        "Server: " + sn.str() + "\r\n"
        "Date: " + get_rfc_date() + "\r\n"
        "Content-Type: " + mime_type + "\r\n"
        "Content-Length: " + std::to_string(bytes_to_send) + "\r\n" +
        "Accept-Ranges: bytes\r\n" + // 🚀 CLAVE 1: Siempre anunciar soporte de rangos
        "X-Content-Type-Options: nosniff\r\n" + // 🚀 CLAVE 2: Forzar el renderizado binario estricto
        extra_headers +
        "Connection: close\r\n\r\n";


    if (!write_all(client_fd, headers.c_str(), headers.length())) {
        close(file_fd);
        shutdown(client_fd, SHUT_RDWR);
        close(client_fd);
        return; 
    }    

    // Terminate immediately without parsing payload if request method is HEAD
    if (request.get_method() == "HEAD") {
        close(file_fd);
        shutdown(client_fd, SHUT_RDWR);
        close(client_fd);
        return;
    }

    // 🚀 NUEVO MOTOR DE TRANSMISIÓN BARE-METAL
    off_t current_offset = offset_start;
    size_t remaining_bytes = bytes_to_send;
    size_t actual_bytes_sent = 0;

    while (remaining_bytes > 0) {
        ssize_t sent = sendfile(client_fd, file_fd, &current_offset, remaining_bytes);
        
        if (sent < 0) {
            // Caso A: Interrupción por señal del sistema. Re-intentamos el tick inmediatamente.
            if (errno == EINTR) {
                continue;
            }
            
            // Caso B: El buffer TCP de la tarjeta de red está lleno (EAGAIN / EWOULDBLOCK).
            // Le damos un micro-respiro de 1ms al hardware para que vacíe la tubería.
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
                continue;
            }

            // Caso C: Un error crítico real (ej. tubería rota o desconexión física)

            if (errno != EPIPE) {
                std::cerr << RED << "[C++ FastPath]" << RESET << "❌ Critical network write failure on sendfile: " << errno << std::endl;
            }
            break;
        }
        
        if (sent == 0) {
            // Llegamos al final inesperado del archivo físico en disco
            break;
        }

        // Caso Feliz: Restamos los bytes despachados con éxito en esta vuelta
        remaining_bytes -= sent;
        actual_bytes_sent += sent;
    }

    try {
        close(file_fd);
    } catch(...) {
        std::cerr << RED << "[C++ FastPath]" << RESET << "❌ Couldn't close file " << request.get_path() << std::endl;
    }
    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);
    // log_msg(RED, "[C++ FastPath]", RESET ," 🚀 Zero-Copy Stream complete (", status_code, ") for asset: ", local_path);
    log_access(request, status_code, actual_bytes_sent);
}

namespace fs = std::filesystem;

std::string url_encode(const std::string& str) {
    std::ostringstream escaped;
    escaped.fill('0');
    escaped << std::hex;
    for (char c : str) {
        if (isalnum(static_cast<unsigned char>(c)) || c == '-' || c == '_' || c == '.' || c == '~') {
            escaped << c;
        } else {
            escaped << std::uppercase << '%' << std::setw(2) << int(static_cast<unsigned char>(c)) << std::nouppercase;
        }
    }
    return escaped.str();
}

void handle_send_dir_cpp(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path) {
    std::error_code ec;
    fs::path dir_path(local_path);

    if (!fs::exists(dir_path, ec) || !fs::is_directory(dir_path, ec)) {
        send_error_html(client_fd, request, 404, "Not Found (Directory does not exist)");
        return;
    }

    std::vector<fs::directory_entry> entries;
    for (const auto& entry : fs::directory_iterator(dir_path, ec)) {
        if (ec) break;
        entries.push_back(entry);
    }

    if (ec) {
        send_error_html(client_fd, request, 500, "Internal Server Error (Directory read failure)");
        return;
    }

    // Sort: directories first, then files alphabetically
    std::sort(entries.begin(), entries.end(), [](const fs::directory_entry& a, const fs::directory_entry& b) {
        if (a.is_directory() != b.is_directory()) return a.is_directory();
        return a.path().filename().string() < b.path().filename().string();
    });

    std::string base_path = web_path;
    if (base_path.back() != '/') base_path += '/';

    std::ostringstream html;
    html << "<!DOCTYPE html>\n<html>\n<head>\n"
         << "<meta charset=\"UTF-8\">\n"
         << "<title>Index of " << web_path << "</title>\n"
         << "<style>\n"
         << "body { font-family: sans-serif; margin: 2rem; background: #fafafa; color: #333; }\n"
         << "h1 { border-bottom: 1px solid #ddd; padding-bottom: 0.5rem; }\n"
         << "a { text-decoration: none; display: inline-block; padding: 2px 0; }\n"
         << "a:hover { text-decoration: underline; }\n"
         << ".dir { color: #d97706; font-weight: bold; }\n"
         << ".file { color: #2563eb; }\n"
         << "</style>\n"
         << "</head>\n<body>\n"
         << "<h1>Index of " << web_path << "</h1>\n"
         << "<ul style=\"list-style-type: none; padding: 0;\">\n";

    // Parent directory link
    if (web_path != "/") {
        html << "<li><a href=\"../\" class=\"dir\">📁 .. (Parent Directory)</a></li>\n";
    }

    for (const auto& entry : entries) {
        std::string filename = entry.path().filename().string();
        std::string display_name = filename;
        std::string encoded_name = url_encode(filename);

        if (entry.is_directory()) {
            display_name += "/";
            encoded_name += "/";
        }

        std::string icon = entry.is_directory() ? "📁" : "📄";
        std::string css_class = entry.is_directory() ? "dir" : "file";

        html << "<li><a href=\"" << base_path << encoded_name << "\" class=\"" << css_class << "\">"
             << icon << " " << display_name << "</a></li>\n";
    }

    html << "</ul>\n"
         << "<hr>\n"
         << "<div style=\"font-size: 0.8rem; color: #666;\">OxiServer/" << VERSION << "</div>\n"
         << "</body>\n</html>\n";

    std::string body = html.str();
    std::string headers = 
        "HTTP/1.1 200 OK\r\n"
        "Date: " + get_rfc_date() + "\r\n"
        "Server: OxiServer/" + VERSION + "\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Content-Length: " + std::to_string(body.length()) + "\r\n"
        "Connection: close\r\n\r\n";

    size_t total_bytes = headers.length() + body.length();
    
    if (write_all(client_fd, headers.c_str(), headers.length()) &&
        write_all(client_fd, body.c_str(), body.length())) {
        // Success
    }

    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);

    log_access(request, 200, total_bytes);
}

void handle_send_dir(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path) {
    bool offloaded_dir = false;

    // Extraemos la información real validada por la clase Request
    std::string path = request.get_path();
    std::string client_ip = request.get_client_ip();

    PyGILState_STATE gstate = PyGILState_Ensure();

    // if (py_send_dir_func != nullptr) {
    //     // Preparamos los argumentos para server.embedded_send_directory_listing:
    //     // (socket_fd, path, client_ip)
    //     PyObject* pFD = PyLong_FromLong(client_fd);
    //     PyObject* pPathStr = PyUnicode_FromString(path.c_str());
    //     PyObject* pIPStr = PyUnicode_FromString(client_ip.c_str());

    //     PyObject* pArgs = PyTuple_New(3);
    //     PyTuple_SetItem(pArgs, 0, pFD);       // Roba referencia
    //     PyTuple_SetItem(pArgs, 1, pPathStr);  // Roba referencia
    //     PyTuple_SetItem(pArgs, 2, pIPStr);    // Roba referencia

    //     PyObject* pResult = PyObject_CallObject(py_send_dir_func, pArgs);
    //     Py_DECREF(pArgs);

    //     if (pResult != nullptr) {
    //         offloaded_dir = true;
    //         Py_DECREF(pResult);
    //     } else {
    //         PyErr_Print();
    //     }
    // }

    PyGILState_Release(gstate);

    // Fallback de texto plano si la máquina virtual de Python no responde
    if (!offloaded_dir) {
        std::string body = "OxiServer Low-Level Directory Listing Fallback for: " + web_path + "\n";
        std::string response = "HTTP/1.1 " + std::to_string(200) + " \r\n"
                               "Date: " + get_rfc_date() + "\r\n"
                               "Content-Type: text/plain; charset=utf-8\r\n"
                               "Content-Length: " + std::to_string(body.length()) + "\r\n"
                               "Connection: close\r\n\r\n" + body;
        send(client_fd, response.c_str(), response.length(), 0);
        close(client_fd);
    }
}

static void reap_child(pid_t pid, int grace_ms = 1000) {
    int status;
    // Give it a moment to exit on SIGTERM.
    for (int waited = 0; waited < grace_ms; waited += 50) {
        pid_t r = waitpid(pid, &status, WNOHANG);
        if (r == pid) return;
        if (r < 0 && errno == ECHILD) return;   // already reaped elsewhere
        if (r < 0 && errno != EINTR) return;    // unexpected
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    kill(pid, SIGKILL);
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
}


std::string build_cgi_response(const std::string& cgi_output, const std::string& default_server_name) {
    // 1. Split the CGI output into Headers and Body
    size_t header_end = cgi_output.find("\r\n\r\n");
    size_t delimiter_len = 4;

    if (header_end == std::string::npos) {
        header_end = cgi_output.find("\n\n");
        delimiter_len = 2;
    }

    if (header_end == std::string::npos) {
        // No header/body boundary found. Treat the whole output as the body.
        std::string body = cgi_output;
        std::string content_type = isHtml(body) ? "text/html;" : "text/plain;";
        return "HTTP/1.1 200 OK\r\n"
               "Server: " + default_server_name + "\r\n"
               "Date: "  + get_rfc_date() + "\r\n"
               "Content-Type: " + content_type + " charset=utf-8\r\n"
               "Content-Length: " + std::to_string(body.length()) + "\r\n"
               "Connection: close\r\n\r\n" + body;
    }

    std::string headers_part = cgi_output.substr(0, header_end);
    std::string body_part = cgi_output.substr(header_end + delimiter_len); // Use dynamic length

    std::string status_line = "HTTP/1.1 200 OK";
    std::string content_type = "text/html; charset=utf-8"; // Default CGI type
    std::string location = "";
    std::ostringstream extra_headers;

    // 2. Parse the headers line by line
    std::istringstream stream(headers_part);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        
        size_t colon = line.find(':');
        if (colon == std::string::npos) continue;

        std::string key = line.substr(0, colon);
        std::string value = line.substr(colon + 1);
        
        // Trim leading whitespace from value
        value.erase(0, value.find_first_not_of(" \t"));

        // Case-insensitive key matching
        std::string lower_key = key;
        std::transform(lower_key.begin(), lower_key.end(), lower_key.begin(), ::tolower);

        if (lower_key == "status") {
            // 🚀 THE FIX: Parse the "Status: 404 Not Found" header
            // If the script just sends "Status: 404", append the default phrase
            if (value.find(' ') == std::string::npos) {
                int code = 0;
                try { code = std::stoi(value); } catch(...) {}
                if (code >= 100 && code < 600) {
                    status_line = "HTTP/1.1 " + value + " " + std::string(strerror(code));
                } else {
                    status_line = "HTTP/1.1 200 OK";
                }
            } else {
                status_line = "HTTP/1.1 " + value;
            }
        } else if (lower_key == "location") {
            location = value;
        } else if (lower_key == "content-type") {
            content_type = value;
        } else {
            // Forward any other custom headers the script emitted (X-Custom, etc.)
            extra_headers << key << ": " << value << "\r\n";
        }
    }

    // 3. Handle Redirects (Location header without a Status header)
    // RFC 3875 says: If Location is set, the response is a 302 redirect.
    if (!location.empty() && status_line == "HTTP/1.1 200 OK") {
        status_line = "HTTP/1.1 302 Found";
    }

    // 4. Assemble the final HTTP Response
    std::ostringstream response;
    response << status_line << "\r\n"
             << "Server: " << default_server_name << "\r\n";
             
    if (!location.empty()) {
        response << "Location: " << location << "\r\n";
    } else {
        // Only send Content-Type if it's not a redirect
        response << "Content-Type: " << content_type << "\r\n";
    }

    response << extra_headers.str()
             << "Content-Length: " << body_part.length() << "\r\n"
             << "Connection: close\r\n\r\n"
             << body_part;

    return response.str();
}

int extract_http_status(std::string_view response) {
    // A valid HTTP status line looks like: "HTTP/1.1 404 Not Found\r\n"
    // Minimum length is roughly 12 chars ("HTTP/1.1 200")
    if (response.size() < 12) return 200;
    
    // Check if it starts with "HTTP/"
    if (response.substr(0, 5) != "HTTP/") return 200;
    
    // Find the first space, which separates the version from the code
    size_t space_pos = response.find(' ');
    if (space_pos == std::string_view::npos) return 200;
    
    // The code is the 3 characters immediately following the space
    if (space_pos + 4 > response.size()) return 200;
    
    std::string_view code_str = response.substr(space_pos + 1, 3);
    
    // Verify the 3 characters are digits
    if (!std::isdigit(code_str[0]) || !std::isdigit(code_str[1]) || !std::isdigit(code_str[2])) {
        return 200;
    }
    
    // Convert to integer. (Simple manual conversion to avoid std::stoi overhead/allocations)
    int code = (code_str[0] - '0') * 100 + 
               (code_str[1] - '0') * 10 + 
               (code_str[2] - '0');
               
    return (code >= 100 && code <= 599) ? code : 200;
}

void handle_cgi(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path) {
    // log_msg("[C++ Native Spawn CGI] Launching sub-process for: ", web_path);



    struct stat path_stat;
    if (stat(local_path.c_str(), &path_stat) != 0) {
        std::string message = "Not Found: " + web_path;
        send_error(client_fd, 404, message.c_str(), request);
        return;
    }

    std::string method = request.get_method();
    std::string query_string = request.get_query_string();
    std::string content_length = request.has_header("content-length") ? request.get_header("content-length") : "0";
    std::string content_type = request.has_header("content-type") ? request.get_header("content-type") : "application/x-www-form-urlencoded";
    std::string script_filename = local_path;
    // std::string request_body = const_cast<Request&>(request).read_body(); // Consume the body destructively

    // Determinar el intérprete adecuado según la extensión del archivo
    size_t dot_pos = local_path.find_last_of('.');
    std::string ext = (dot_pos != std::string::npos) ? local_path.substr(dot_pos) : "";
  
    std::vector<std::string> env_storage;
    std::vector<char*> envp;
    auto add = [&](const std::string& s) { env_storage.push_back(s); };

    // Copy parent env (filtered), then override/add CGI vars.
    for (char** e = environ; *e; ++e) {
        std::string kv(*e);
        // Skip any HTTP_* / CGI vars that might have been leaked
        if (kv.rfind("HTTP_", 0) == 0 || kv.rfind("CONTENT_", 0) == 0 ||
            kv.rfind("REQUEST_", 0) == 0 || kv.rfind("SCRIPT_", 0) == 0 ||
            kv.rfind("QUERY_", 0) == 0 || kv.rfind("SERVER_", 0) == 0 ||
            kv.rfind("REMOTE_", 0) == 0 || kv.rfind("GATEWAY_", 0) == 0)
            continue;
        add(kv);
    }

    // 1. Configurar las variables de entorno CGI/1.1 de forma segura antes del spawn
    std::ostringstream ss;
    ss << "OxiServer/" << VERSION <<  " (C++/Julia Powered)";
    add("SERVER_SOFTWARE=" + ss.str());
    std::ostringstream sn;
    sn << "OxiServer/" << VERSION << "";
    add("SERVER_NAME=" +  sn.str());
    add("GATEWAY_INTERFACE=CGI/1.1");
    add("REQUEST_METHOD=" + method);
    add("QUERY_STRING=" + query_string);
    add("CONTENT_LENGTH=" + content_length);
    add("CONTENT_TYPE=" + content_type);
    add("SCRIPT_FILENAME=" + script_filename);
    add("SERVER_PROTOCOL=HTTP/1.1");
    add("REMOTE_ADDR=" + const_cast<Request&>(request).get_client_ip());
    // 🚀 CGI/1.1 Environment Variables
    // DOCUMENT_ROOT: physical path of the web root (no trailing slash)
    std::string doc_root = get_config_string("static_dir", "static");
    if (!doc_root.empty() && doc_root.back() == '/') doc_root.pop_back();
    add("DOCUMENT_ROOT=" + doc_root);
    // SCRIPT_NAME: web-relative path of the script (e.g. "/cgi-bin/foo.py")
    add("SERVER_PROTOCOL=HTTP/1.1");
    add("REMOTE_ADDR=" + const_cast<Request&>(request).get_client_ip());
    if (is_php(web_path)) {
        add("REDIRECT_STATUS=200");
        add("PHP_SELF=" + script_filename);
    }

    // SCRIPT_NAME: web-relative path of the script
    // Derived from web_path (full request URI) minus the PATH_INFO suffix
    // Example: web_path = "/cgi-bin/script.py/foo/bar"
    //          script_name = "/cgi-bin/script.py"
    //          path_info = "/foo/bar"
    std::string script_name = web_path;
    std::string path_info = "";
    
    // The script name is web_path truncated at the length of the script filename.
    // script_filename (local) = "static/cgi-bin/script.py"
    // We need to map it back to web form. Easier: strip the static_dir prefix
    // from script_filename, then strip that from web_path.
    std::string static_dir = get_config_string("static_dir", "static");
    if (!static_dir.empty() && static_dir.back() == '/') static_dir.pop_back();
    
    if (script_filename.rfind(static_dir, 0) == 0) {
        std::string script_web_part = script_filename.substr(static_dir.length()); // e.g. "/cgi-bin/script.py"
        if (web_path.rfind(script_web_part, 0) == 0) {
            script_name = script_web_part;
            path_info = web_path.substr(script_web_part.length()); // e.g. "/foo/bar"
        }
    }
    
    add("SCRIPT_NAME=" + script_name);
    add("PATH_INFO=" + path_info);    


    for (auto& s : env_storage) envp.push_back(const_cast<char*>(s.c_str()));
    envp.push_back(nullptr);

    // 2. Crear las tuberías de comunicación nativas (POSIX Pipes)
    int stdin_pipe[2];  // Servidor escribe (1) -> Subproceso lee (0)
    int stdout_pipe[2]; // Subproceso escribe (1) -> Servidor lee (0)

    if (pipe(stdin_pipe) < 0) { 
        send_error(client_fd, 500, "Internal Server Error (Stdin pipe allocation failed)", request);
        return;
    }
    if (pipe(stdout_pipe) < 0) { 
        close(stdin_pipe[0]); 
        close(stdin_pipe[1]); 
        send_error(client_fd, 500, "Internal Server Error (Stdout pipe allocation failed)", request);
        return; 
    }

    // 3. Configurar las acciones de duplicación de descriptores para posix_spawn
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);

    // Redirigir el stdin y stdout dentro del nuevo proceso clonado de forma atómica
    posix_spawn_file_actions_adddup2(&actions, stdin_pipe[0], STDIN_FILENO);
    posix_spawn_file_actions_adddup2(&actions, stdout_pipe[1], STDOUT_FILENO);

    // Cerrar los descriptores redundantes en el hijo para evitar fugas y deadlocks
    posix_spawn_file_actions_addclose(&actions, stdin_pipe[1]);
    posix_spawn_file_actions_addclose(&actions, stdout_pipe[0]);

    pid_t pid;
    int spawn_result = -1;


    // 4. Invocar el ejecutable usando posix_spawn (Sin duplicar memoria ni congelar hilos de Python)
    std::string executable;

    posix_spawnattr_t attr;
    posix_spawnattr_init(&attr);
    sigset_t empty;
    sigemptyset(&empty);
    posix_spawnattr_setsigmask(&attr, &empty);
    posix_spawnattr_setpgroup(&attr, 0);
    posix_spawnattr_setflags(&attr, POSIX_SPAWN_SETSIGMASK | POSIX_SPAWN_SETPGROUP);

    if (ext.empty() || !cgi_handlers.contains(ext)) {
        if (access(local_path.c_str(), X_OK)) {
            std::string err_msg = "Resource " + web_path + " is not executable.";
            send_error(client_fd, 500, err_msg.c_str(), request);  
            posix_spawnattr_destroy(&attr);
            return;
        } else {
            executable = local_path;
            char* argv[] = {(char*)executable.c_str(), NULL};
            spawn_result = posix_spawn(&pid, executable.c_str(), &actions, &attr, argv, envp.data());
            posix_spawnattr_destroy(&attr);
            #ifndef __NDEBUG__
            log_msg(YELLOW, "[DEBUG]", RESET, " Executing: ", executable);
            #endif
        }
    } else {
        executable = cgi_handlers[ext];
        char* argv[] = {(char*)executable.c_str(), (char*)local_path.c_str(), NULL};
        spawn_result = posix_spawn(&pid, executable.c_str(), &actions, &attr, argv, envp.data());
        posix_spawnattr_destroy(&attr);
        #ifndef __NDEBUG__
        log_msg(YELLOW, "[DEBUG]", RESET, " Executing: ", executable, " ", local_path);
        #endif
    }


    // Liberar las estructuras de acciones de posix_spawn de inmediato
    posix_spawn_file_actions_destroy(&actions);

    if (spawn_result != 0) {
        close(stdin_pipe[0]); close(stdin_pipe[1]);
        close(stdout_pipe[0]); close(stdout_pipe[1]);
        send_error(client_fd, 502, "Bad Gateway (Failed to spawn CGI subprocess)", request);
        return;
    }

    // 🚀 CONTEXTO DEL PADRE (C++ PRINCIPAL): Cerrar de inmediato los extremos que usa el hijo
    close(stdin_pipe[0]);
    close(stdout_pipe[1]);


    // STEP A: WRITE REQUEST BODY TO PROCESS STDIN

    //Alternative 0: Use a generator.
    size_t current_body_size = 0;
    const long MAX_BODY_LENGTH = get_config_long("max_body_size", 65536); // Example 10MB Limit
    #ifndef __NDEBUG__
        log_msg(YELLOW, "[DEBUG]", RESET, "MAX_BODY_LENGTH: ", MAX_BODY_LENGTH);
    #endif

    bool overflowed = false;

    // Consume chunks lazily as they arrive from the network interface
    for (std::string_view chunk : const_cast<Request&>(request).stream_body()) {
        current_body_size += chunk.size();

        if (current_body_size >= static_cast<size_t>(MAX_BODY_LENGTH)) {
            overflowed = true;
            break; // 💡 Exiting the loop immediately destroys the generator state safely!
        }

        // Pipe the chunk data directly to PHP-CGI or your target sub-process
        write(stdin_pipe[1], chunk.data(), chunk.size());
    }

    if (overflowed) {
        // 1. Forcefully terminate the hanging CGI child process
        killpg(pid, SIGTERM); 
        close(stdin_pipe[1]);
        close(stdout_pipe[0]);

        // 2. Reap the process to prevent it from becoming a zombie
        reap_child(pid);

        log_msg(RED, pad_left("[DEBUG]"), RESET, " Request body too large: ", RED, current_body_size, RESET, " bytes.   /   ", "Closed CGI Process: ", pid);
        // Send a 413 Payload Too Large (or 431 Request Header Fields Too Large)
        send_error(client_fd, 413,  "Request body too long", request);

        return;
    }


    // Alternative I: piping.
    // const_cast<Request&>(request).pipe_body(stdin_pipe[1]);

    // Alternative II: getting request body and then writing it to body. 
    // std::string body = const_cast<Request&>(request).read_body(); 
    // if (!body.empty()) {
    //     write(stdin_pipe[1], body.data(), body.length());
    // }

    // Forzar el fin de archivo (EOF) para que el intérprete empiece a procesar la entrada
    close(stdin_pipe[1]); 

    // STEP B: ABSORBER LA SALIDA EMITIDA POR EL SUBPROCESO
    std::string cgi_output = "";
    char read_buffer[4096];
    ssize_t bytes_read;
    
    // Al haber cerrado stdout_pipe[1] arriba, este bucle se destrabará con 0 (EOF) 
    // en el milisegundo exacto en que el script de Python termine de imprimir
    while ((bytes_read = read(stdout_pipe[0], read_buffer, sizeof(read_buffer) - 1)) > 0) {
        read_buffer[bytes_read] = '\0';
        cgi_output.append(read_buffer, bytes_read);
    }
    close(stdout_pipe[0]);

    // Esperar y limpiar las estructuras del proceso hijo de forma síncrona
    int status;
    waitpid(pid, &status, 0);

    if (cgi_output.empty()) {
        send_error(client_fd, 502, "Bad Gateway (Subprocess aborted without sending output data)", request);
        return;
    }

    int total_bytes = 0;
    
    // 🚀 NEW: Parse the CGI output using the standard specification
    std::string full_response = build_cgi_response(cgi_output, sn.str());

    // Send the fully-formed response directly to the client
    if (!write_all(client_fd, full_response.data(), full_response.size())) {
        // Client disconnected early
    }
    
    size_t body_start = full_response.find("\r\n\r\n");
    if (body_start != std::string::npos) {
        total_bytes = full_response.size() - (body_start + 4);
    } else {
        total_bytes = full_response.size(); // Fallback if headers are malformed
    }

    shutdown(client_fd, SHUT_RDWR);
    close(client_fd);

    int status_code = extract_http_status(full_response);
    log_access(request, status_code, total_bytes); 
}

void offload_to_python_asgi(int client_fd) {
    bool offloaded_to_python = false;

    // 🚀 INTERCEPT DEFENSIVELY: If no dynamic app target is active, fire a clean 404 response
    if (!has_application_target || py_asgi_app_object == nullptr) {
        Request mock_req("GET", "/", "HTTP/1.1");
        send_error(client_fd, 404, "Not Found (No ASGI Application Hosted)", mock_req);
        return;
    }

    #ifndef __NDEBUG__
    log_msg(YELLOW, "[DEBUG]", RESET, "Inside offload_to_python_asgi", '@', "Acquiring GIL lock");
    #endif

    PyGILState_STATE gstate = PyGILState_Ensure();

    #ifndef __NDEBUG__
    log_msg(YELLOW, "[DEBUG]", RESET, "Inside offload_to_python_asgi", '@', "Just acquired GIL lock");
    #endif

    if (py_run_from_socket_func != nullptr) {
        PyObject* pFD = PyLong_FromLong(client_fd);
        PyObject* pFuncArgs = PyTuple_New(2); 
        PyTuple_SetItem(pFuncArgs, 0, pFD);                   
        Py_XINCREF(py_asgi_app_object);
        PyTuple_SetItem(pFuncArgs, 1, py_asgi_app_object);   

        PyObject* pResult = PyObject_CallObject(py_run_from_socket_func, pFuncArgs);
        Py_DECREF(pFuncArgs);

        if (pResult != nullptr) {
            offloaded_to_python = true;
            Py_DECREF(pResult);
        } else {
            #ifndef __NDEBUG__
            log_msg(YELLOW, "[DEBUG]", RESET, "Inside offload_to_python_asgi", '@', "Couldn't run py_run_from_socket_func");
            #endif
            PyErr_Print();
        }
    }

    #ifndef __NDEBUG__
    log_msg(YELLOW, "[DEBUG]", RESET, "Inside offload_to_python_asgi", '@', "About to release GIL lock");
    #endif
    PyGILState_Release(gstate);
    #ifndef __NDEBUG__
    log_msg(YELLOW, "[DEBUG]", RESET, "Inside offload_to_python_asgi", '@', "GIL lock released");
    #endif

    if (!offloaded_to_python) {
       Request mock_req("GET", "/", "HTTP/1.1");        
        send_error(client_fd, 500, "Internal Server Error (Oxi Embedded Pipeline Failed)", mock_req);
    }
}

void handle_client(int client_fd) {
    std::string request_line = peek_request_line(client_fd);
    
    if (request_line.empty()) {
        // 🚀 We failed to parse the request. We don't have a Request object.
        // But we DO have whatever bytes came in. Let's log them.
        char peek_buffer[1024]; 
        ssize_t received = recv(client_fd, peek_buffer, sizeof(peek_buffer) - 1, MSG_PEEK);
        
        std::string raw_context = "Unknown/Error";
        if (received > 0) {
            peek_buffer[received] = '\0';
            raw_context = std::string(peek_buffer);
            // Trim to a reasonable length for the HTML/log
            if (raw_context.length() > 80) raw_context = raw_context.substr(0, 80) + "...";
        }

        // Build a mock showing what we got
        Request mock_req("UNKNOWN", raw_context, "HTTP/1.1");
        send_error(client_fd, 400, "Bad Request (Malformed HTTP Headers)", mock_req);
        return;
    }

    std::istringstream request_stream(request_line);
    std::string method, path, protocol, query_string;
    
    // Note: The >> operator doesn't throw, so try/catch is not needed here.
    // If parsing fails, the strings remain empty.
    request_stream >> method >> path >> protocol;

    size_t query_pos = path.find('?');
    if (query_pos != std::string::npos) {
        query_string = path.substr(query_pos + 1);
        path = path.substr(0, query_pos);
    }

    // 🚀 If method/path/protocol are empty, the line was garbage.
    if (method.empty() || path.empty() || protocol.empty()) {
        Request mock_req("UNKNOWN", request_line, "HTTP/1.1");
        send_error(client_fd, 400, "Bad Request (Malformed HTTP Headers)", mock_req);
        return;
    }

    std::string local_physical_path = "";
    int static_check_result = is_static(path, local_physical_path);
    
    if (static_check_result == 200) {
        // 🚀 The real Request object. Since we used MSG_PEEK, the socket 
        // still holds the full request. This call will read the headers.
        Request request(client_fd);
        handle_static(client_fd, request, local_physical_path, path); 
        return;
    } else if (static_check_result == 403) {
        Request request(client_fd);
        send_error(client_fd, 403, "Forbidden (Static/CGI Access Denied)", request);
        return;
    }

    offload_to_python_asgi(client_fd);
}

void start_server(const std::string& host, int port) {
    log_msg(BLUE, "[Server]", RESET, " Waiting for Python initialization pipeline...");
    while (!python_ready) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    struct addrinfo hints{}, *res = nullptr, *p = nullptr;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;

    std::string port_str = std::to_string(port);
    const char* node = host.empty() ? nullptr : host.c_str();

    int status = getaddrinfo(node, port_str.c_str(), &hints, &res);
    if (status != 0) {
        log_msg(RED, "[Server]", RESET, " getaddrinfo failed: ", gai_strerror(status));
        return;
    }

    for (p = res; p != nullptr; p = p->ai_next) {
        server_fd = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (server_fd < 0) continue;

        int opt = 1;
        setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

        if (bind(server_fd, p->ai_addr, p->ai_addrlen) == 0) {
            break;
        }
        close(server_fd);
        server_fd = -1;
    }

    freeaddrinfo(res);

    if (server_fd < 0) {
        log_msg(RED, "[Server]", RESET, " Failed to bind to ", host, ":", port);
        return;
    }

    if (listen(server_fd, 128) < 0) {
        log_msg(RED, "[Server]", RESET, " Failed to listen on socket.");
        close(server_fd);
        return;
    }

    log_msg(BLUE, "[Server]", RESET, " (PID ", getpid(), ") Listening on ", host, ":", port, " Awaiting requests...\n");

    while (server_running) {
        int client_fd = accept(server_fd, nullptr, nullptr);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            break;
        }

        try {
            std::thread t(handle_client, client_fd);
            t.detach();
        } catch (const std::system_error& e) {
            log_msg(RED, "[Server]", RESET, " Failed to spawn thread: ", e.what());
            close(client_fd);
        }
    }

    // 🚀 SHUTDOWN SEQUENCE
    // Wait up to 5 seconds for detached threads to finish gracefully.
    // This prevents Py_FinalizeEx() from tearing down the interpreter 
    // while threads are still running Python code (which would segfault).
    log_msg("[Server] Waiting for active connections to finish...");
    
    std::unique_lock<std::mutex> lock(shutdown_mutex);
    if (!shutdown_cv.wait_for(lock, std::chrono::seconds(5), []{ return active_connections == 0; })) {
        log_msg(RED, "[Server] Timeout waiting for connections to close. Forcing exit.");
    }
}

void handle_sigint(int sig) {
    int saved_errno = errno;
    if (signal_pipe[1] != -1) {
        char byte = 'X';
        [[maybe_unused]] ssize_t result = write(signal_pipe[1], &byte, 1);
    }
    errno = saved_errno;
}

void signal_worker() {
    char buf[1];
    struct pollfd pfd;
    pfd.fd = signal_pipe[0];
    pfd.events = POLLIN;

    // Block indefinitely until a signal writes to the pipe
    int ret = poll(&pfd, 1, -1);

    if (ret > 0 && (pfd.revents & POLLIN)) {
        ssize_t n = read(signal_pipe[0], buf, 1);
        if (n > 0) {
            log_msg("\n", BLUE , "[Signal]", RESET, " Shutdown initiated via signal (or manual trigger)...");
            shutdown_requested = true;
            server_running = false;

            // Wake up the accept() loop
            if (server_fd >= 0) {
                shutdown(server_fd, SHUT_RDWR);
                close(server_fd);
                server_fd = -1;
            }

            // Safely stop the Python loop
            PyGILState_STATE gstate = PyGILState_Ensure();
            PyRun_SimpleString(
                "import asyncio\n"
                "import server\n"
                "async def _stop_server():\n"
                "    if hasattr(server, '_lifespan_q'):\n"
                "        await server._lifespan_q.put({'type': 'lifespan.shutdown'})\n"
                "        await server._lifespan_ev.wait()\n"
                "        await server._lifespan_task\n"
                "    server._embedded_global_loop.stop()\n"
                "asyncio.run_coroutine_threadsafe(_stop_server(), server._embedded_global_loop)\n"
            );
            PyGILState_Release(gstate);        }
    }
}

namespace fs = std::filesystem;
std::filesystem::path get_executable_dir() {
#ifdef _WIN32
    char buffer[MAX_PATH];
    GetModuleFileNameA(NULL, buffer, MAX_PATH);
    return fs::path(buffer).parent_path();
#elif defined(__APPLE__)
    char buffer[1024];
    uint32_t size = sizeof(buffer);
    if (_NSGetExecutablePath(buffer, &size) == 0) {
        return fs::canonical(buffer).parent_path();
    }
    return fs::current_path();
#else
    // Linux
    std::error_code ec;
    fs::path p = fs::read_symlink("/proc/self/exe", ec);
    if (!ec) {
        return p.parent_path();
    }
    return fs::current_path(); // Fallback
#endif
}

std::string get_py_version() {
    // 1. Try current directory first (for dev mode)
    std::ifstream file("__about__.py");
    
    // 2. If not found, try the executable's directory
    if (!file.is_open()) {
        fs::path exe_dir = get_executable_dir();
        file.open(exe_dir / "__about__.py");
    }
    
    if (!file.is_open()) return "";

    std::string line;
    std::regex version_regex(R"(__version__\s*=\s*['"]([^'"]+)['"])");
    std::smatch match;

    while (std::getline(file, line)) {
        if (std::regex_search(line, match, version_regex)) {
            return match[1].str();
        }
    }
    return "";
}

void print_usage(const char* prog_name) {
    std::cout << "Usage: " << prog_name << " [OPTIONS] [APP_TARGET]\n\n"
              << "OxiServer: Hybrid C++/Embedded-Python Web Server\n\n"
              << "Options:\n"
              << "  -h, --host HOST        Bind socket to HOST (default: 0.0.0.0)\n"
              << "  -p, --port PORT        Bind socket to PORT (default: 8086)\n"
              << "  -w, --workers N        Number of workers (reserved for future use)\n"
              << "      --version          Show version and exit\n"
              << "      --help             Show this help message and exit\n"
              << "\n"
              << "Arguments:\n"
              << "  APP_TARGET             Python module (default: static:static_app)\n"
              << "                         Example: apps.demo:app\n";
}

int main(int argc, char* argv[]) {
    // --- 1. CLI PARSING ---
    std::string bind_host = "0.0.0.0";
    int bind_port = 8086;
    bool show_version = false;

    static struct option long_options[] = {
        {"host",    required_argument, 0, 'h'},
        {"port",    required_argument, 0, 'p'},
        {"workers", required_argument, 0, 'w'},
        {"version", no_argument,       0, 'v'},
        {"help",    no_argument,       0, '?'},
        {0, 0, 0, 0}
    };

    int opt;
    int option_index = 0;
    // "h:p:w:v?" means: h, p, w require an argument. v, ? do not.
    while ((opt = getopt_long(argc, argv, "h:p:w:v?", long_options, &option_index)) != -1) {
        switch (opt) {
            case 'h':
                bind_host = optarg;
                break;
            case 'p':
                try {
                    bind_port = std::stoi(optarg);
                    if (bind_port < 1 || bind_port > 65535) {
                        std::cerr << "Error: Port must be between 1 and 65535.\n";
                        return 1;
                    }
                } catch (...) {
                    std::cerr << "Error: Invalid port number: " << optarg << "\n";
                    return 1;
                }
                break;
            case 'w':
                // Reserved for future multi-worker support
                break;
            case 'v':
                show_version = true;
                break;
            case '?':
                print_usage(argv[0]);
                return (optopt == '?') ? 0 : 1;
            default:
                print_usage(argv[0]);
                return 1;
        }
    }

    if (show_version) {
       std::string py_version = get_py_version();
        if (py_version.empty()) py_version = "0.0.1";
        std::cout << "OxiServer " << py_version << " (C++/Julia Powered ASGI Engine)\n";
        return 0;
    }
    
    // --- 2. POSITIONAL ARGUMENT (APP TARGET) ---
    // getopt_long leaves non-option arguments starting at argv[optind].
    if (optind < argc) {
        app_target_string = argv[optind];
        has_application_target = true;
    } else {
        app_target_string = "static:static_app";
        has_application_target = true;
    }

    // --- 3. SYSTEM SETUP (Pipe & Signals) ---
    if (pipe(signal_pipe) != 0) {
        std::cerr << "Failed to create signal pipe\n";
        return 1;
    }
    fcntl(signal_pipe[0], F_SETFL, O_NONBLOCK);
    fcntl(signal_pipe[1], F_SETFL, O_NONBLOCK);

    signal(SIGINT, handle_sigint);
    signal(SIGTERM, handle_sigint);

    // --- 4. ENVIRONMENT PROBING ---
    probe_php_runtime();
    probe_cgi_handlers();
    clear_screen();

    if (!PHP_BINARY_PATH.empty()) {
        log_msg('\n', YELLOW, "PHP execution runtime: ", RESET, PHP_BINARY_PATH);
    } else {
        log_msg("PHP execution runtime not installed.");
    }

    // --- 5. PYTHON INIT & THREADS ---
    Py_Initialize();
    log_msg(GREEN, "[C++]", RESET, " Python interpreter initialized.");

    PyThreadState* main_thread_state = PyEval_SaveThread();
    
    // Start the Python loop thread (global variable)
    python_loop_thread = std::thread(init_python_objs);

    // Start the signal worker thread (local variable)
    std::thread signal_thread(signal_worker);

    // --- 6. START THE SERVER ---
    // We must pass the parsed host and port to start_server.
    start_server(bind_host, bind_port);

    // --- 7. SHUTDOWN SEQUENCE ---
    // If the server died for a reason OTHER than a signal, the signal_thread 
    // is still waiting on the pipe. We must write a dummy byte to wake it up.
    if (server_running) {
        char wake = 'X';
        [[maybe_unused]] ssize_t _ = write(signal_pipe[1], &wake, 1);
    }

    // Join the threads cleanly
    if (signal_thread.joinable()) signal_thread.join();
    if (python_loop_thread.joinable()) python_loop_thread.join();    

    // --- 7. SHUTDOWN SEQUENCE ---
    if (server_running) {
        char wake = 'X';
        [[maybe_unused]] ssize_t _ = write(signal_pipe[1], &wake, 1);
    }
    if (signal_thread.joinable()) signal_thread.join();
    if (python_loop_thread.joinable()) python_loop_thread.join();

    PyEval_RestoreThread(main_thread_state);
    
    Py_XDECREF(py_asgi_app_object);
    Py_XDECREF(py_run_from_socket_func);
    Py_XDECREF(py_server_config);
    Py_XDECREF(py_server_version);
    Py_XDECREF(py_loop_object);
    // Py_XDECREF(py_send_error_func);

    std::cout << std::flush;
    std::cerr << std::flush;

    Py_FinalizeEx();

    log_msg(GREEN, "[C++]", RESET, " Server finalized cleanly. Goodbye!");
    return 0;
}


