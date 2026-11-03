#ifndef __WEB_SERVER_HPP__

#define __WEB_SERVER_HPP__

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#undef vector 

#include <filesystem>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <syncstream>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
#include <string>
#include <string_view>
#include <cstring>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <utility>
#include <variant>
#include <condition_variable>
#include <unordered_set>
#include <unordered_map>
#include <fstream>
#include <regex>

#include <limits.h>
#include <netdb.h>
#include <getopt.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/sendfile.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <spawn.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <poll.h>

#ifdef _WIN32
    #include <windows.h>
#elif defined(__APPLE__)
    #include <mach-o/dyld.h>
#endif

#define __NDEBUG__

#define RESET   "\033[0m"

#define BLACK   "\033[30m"
#define RED     "\033[31m"
#define GREEN   "\033[32m"
#define YELLOW  "\033[33m"
#define BLUE    "\033[34m"
#define MAGENTA "\033[35m"
#define CYAN    "\033[36m"
#define WHITE   "\033[37m"

extern std::atomic<int> active_connections;
extern std::mutex shutdown_mutex;
extern std::condition_variable shutdown_cv;

struct ConnectionGuard {
    ConnectionGuard() { active_connections++; }
    ~ConnectionGuard() {
        active_connections--;
        if (active_connections == 0) {
            std::lock_guard<std::mutex> lock(shutdown_mutex);
            shutdown_cv.notify_one();
        }
    }
};

// RAII Guard to ensure CWD is restored automatically on scope exit
struct CwdGuard {
    std::filesystem::path original_path;
    
    CwdGuard() {
        original_path = std::filesystem::current_path();
    }
    
    ~CwdGuard() {
        std::filesystem::current_path(original_path);
    }
};

typedef struct sock_thread {
    int sock;
    std::thread th;
} sock_thread_t;

extern std::unordered_map<std::string, std::string> cgi_handlers;

#include "request.hpp"

// --- Function Prototypes ---
template <typename... Args>
void log_msg(Args&&... args);
void log_access(const Request& request, int status_code, int bytes_sent);

std::string which(const std::string&);

std::string get_rfc_date();
void handle_sendfile(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path);
void handle_send_dir_cpp(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path);
void handle_send_dir(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path);
void handle_cgi(int client_fd, const Request& request, const std::string& local_path, const std::string& web_path);

#endif // __WEB_SERVER_HPP__