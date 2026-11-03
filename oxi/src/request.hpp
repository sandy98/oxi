#ifndef __REQUEST_HPP__
#define __REQUEST_HPP__

#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <unordered_map>
#include <generator>
#include <string_view>
#include <algorithm>

#include <sys/socket.h>
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>

template <typename... Args>
void log_msg(Args&&... args);

class Request {
private:
    int socket_fd;
    size_t buffer_pos = 0;
    size_t buffer_size = 0;
    static const size_t CHUNK_SIZE = 8192; // 8KB is standard for HTTP headers
    std::vector<char> buffer;

    std::string method {"GET"};
    std::string path {"/"};
    std::string query_string {""};
    std::string protocol {"HTTP/1.1"};
    std::string client_ip {"127.0.0.1"};
    std::string raw_body {""};

    std::unordered_map<std::string, std::string> headers;

    bool malformed {false};
    bool body_consumed {false};

    void read_headers() {
        std::string raw_headers;
        const std::string delim = "\r\n\r\n";
        
        while (true) {
            if (buffer_pos < buffer_size) {
                std::string current_view(buffer.data() + buffer_pos, buffer_size - buffer_pos);
                size_t delim_pos = current_view.find(delim);

                if (delim_pos != std::string::npos) {
                    size_t bytes_to_copy = delim_pos + delim.length();
                    raw_headers.append(buffer.data() + buffer_pos, bytes_to_copy);
                    buffer_pos += bytes_to_copy; // Leaves the body start at buffer_pos
                    break;
                }

                raw_headers.append(buffer.data() + buffer_pos, buffer_size - buffer_pos);
                buffer_pos = 0;
                buffer_size = 0;
            }

            ssize_t bytes_received = recv(socket_fd, buffer.data(), buffer.size(), 0);
            if (bytes_received <= 0) {
                // Connection closed or error before headers completed
                break; 
            }

            buffer_pos = 0;
            buffer_size = bytes_received;
        }
        if (raw_headers.empty()) {
            malformed = true;
            return;
        }
        // Parse the request line
        std::istringstream header_stream(raw_headers);
        std::string request_line;
        if (std::getline(header_stream, request_line)) {
            if (!request_line.empty() && request_line.back() == '\r') {
                request_line.pop_back(); // Remove trailing '\r'    
            }
            std::istringstream line_stream(request_line);
            try {
                line_stream >> method >> path >> protocol;
                size_t q_pos = path.find('?');
                if (q_pos != std::string::npos) {
                    query_string = path.substr(q_pos + 1);
                    path = path.substr(0, q_pos);
                }
            } catch (...) {
                malformed = true;
                return;
            }
        } else {
            malformed = true;
            return;
        }

        // Parse headers
        std::string line;
        while (std::getline(header_stream, line) && line != "\r") {
            if (!line.empty() && line.back() == '\r') {
                line.pop_back(); // Remove trailing '\r'
            }
            size_t colon_pos = line.find(':');
            if (colon_pos != std::string::npos) {
                std::string key = line.substr(0, colon_pos);
                std::string value = line.substr(colon_pos + 1);
                // Trim whitespace from value
                value.erase(0, value.find_first_not_of(" \t"));
                value.erase(value.find_last_not_of(" \t") + 1);
                // Convert key to lowercase for case-insensitive matching
                for (auto& c : key) c = std::tolower(c);
                headers[key] = value;
            }
        }

        if (headers.contains("x-real-ip")) {
            client_ip = headers["x-real-ip"];
        } else if (headers.contains("x-forwarded-for")) {
            std::string xff = headers["x-forwarded-for"];
            size_t comma_pos = xff.find(',');
            client_ip = (comma_pos != std::string::npos) ? xff.substr(0, comma_pos) : xff;
        } else {
            // Fallback a la IP física del socket descriptor
            sockaddr_in peer_addr;
            socklen_t addr_len = sizeof(peer_addr);
            if (getpeername(socket_fd, (struct sockaddr*)&peer_addr, &addr_len) == 0) {
                client_ip = inet_ntoa(peer_addr.sin_addr);
            }
        }

    }


public:
    Request() = delete; // Disable default constructor
    explicit Request(int fd) : socket_fd(fd), buffer(CHUNK_SIZE) {
        read_headers();
    }

        // 🚀 Mock constructor: For generating synthetic requests for error handlers
    // and logs when a real request could not be parsed.
    Request(std::string method_, std::string path_, std::string protocol_, 
            std::string client_ip_ = "127.0.0.1") 
        : socket_fd(-1), 
          method(std::move(method_)), 
          path(std::move(path_)), 
          protocol(std::move(protocol_)), 
          client_ip(std::move(client_ip_)) 
    {
        // We skip read_headers() entirely.
        // The object is fully formed from the arguments.
        malformed = false;
        body_consumed = true; // Prevent accidental socket reads
    }

    bool is_malformed() const {
        return malformed;
    }

    // 1. Reads until "\r\n\r\n" and returns the complete raw header string
    // 2. Reads the exact remaining HTTP body based on Content-Length

    std::string get_method() const { 
        return method; 
    }

    std::string get_path() const { 
        return path; 
    }

    std::string get_query_string() const { 
        return query_string; 
    }

    std::string get_protocol() const { 
        return protocol; 
    }

    std::string get_client_ip() const { 
        return client_ip; 
    }

    std::string get_request_line() const {
        std::ostringstream ss;
        std::string qs = get_query_string();
        ss << '"' << get_method() << " " << get_path() << (qs.empty() ? "" : "?") << (qs.empty() ? "" : qs) << " " << get_protocol() << '"';
        return ss.str();
    }

    bool has_header(const std::string& key) const {
        std::string low_key = key;
        for (auto& c : low_key) c = std::tolower(c);
        return headers.contains(low_key);
    }

    std::string get_header(const std::string& key) const {
        std::string low_key = key;
        for (auto& c : low_key) c = std::tolower(c);
        auto it = headers.find(low_key);
        return (it != headers.end()) ? it->second : std::string("");
    }

    std::string get_content_type() const {
        return get_header("content-type");
    }

    std::string get_content_length() const {
        return get_header("content-length");
    }

    // --- Overload 1: For memory-buffered lookups ---
    std::string read_body() {
        if (body_consumed) {
            return raw_body;
        }

        size_t content_length = 0;
        if (malformed || !has_header("content-length")) {
            body_consumed = true;
            return raw_body;
        }

        try {
            content_length = std::stoul(get_header("content-length"));
        } catch (...) {
            body_consumed = true;
            return raw_body;
        }

        if (content_length == 0 || (method != "POST" && method != "PUT" && method != "PATCH")) {
            body_consumed = true;
            return raw_body;
        }

        raw_body.reserve(content_length);

        // Consume what's left in the header buffer
        if (buffer_pos < buffer_size) {
            size_t bytes_available = buffer_size - buffer_pos;
            size_t bytes_to_copy = std::min(bytes_available, content_length);
            raw_body.append(buffer.data() + buffer_pos, bytes_to_copy);
            buffer_pos += bytes_to_copy;
        }

        // Pull remaining chunks directly from socket into the string
        while (raw_body.size() < content_length) {
            size_t remaining = content_length - raw_body.size();
            size_t read_size = std::min(buffer.size(), remaining);
            
            ssize_t bytes_received = recv(socket_fd, buffer.data(), read_size, 0);
            if (bytes_received <= 0) break;
            
            raw_body.append(buffer.data(), bytes_received);
        }

        body_consumed = true;
        return raw_body;
    }

    // --- Overload 2: For streaming zero-copy I/O straight to a pipe/file descriptor ---
    void read_body(int dest_fd) {
        if (dest_fd <= 0) return;

        FILE* fp = fdopen(dest_fd, "w");
        if (!fp) return;

        // If already in memory, flush it straight to the file descriptor
        if (body_consumed) {
            if (!raw_body.empty()) {
                fwrite(raw_body.data(), raw_body.size(), 1, fp);
                fflush(fp);
            }
            fclose(fp);
            return;
        }

        size_t content_length = 0;
        if (malformed || !has_header("content-length")) {
            body_consumed = true;
            fclose(fp);
            return;
        }

        try {
            content_length = std::stoul(get_header("content-length"));
        } catch (...) {
            body_consumed = true;
            fclose(fp);
            return;
        }

        if (content_length == 0 || (method != "POST" && method != "PUT" && method != "PATCH")) {
            body_consumed = true;
            fclose(fp);
            return;
        }

        size_t total_bytes_written = 0;

        // Flush leftover buffer segments straight to destination file descriptor
        if (buffer_pos < buffer_size) {
            size_t bytes_available = buffer_size - buffer_pos;
            size_t bytes_to_copy = std::min(bytes_available, content_length);
            
            fwrite(buffer.data() + buffer_pos, bytes_to_copy, 1, fp);
            fflush(fp);
            
            total_bytes_written += bytes_to_copy;
            buffer_pos += bytes_to_copy;
        }

        // Pipeline loop using a dedicated tracker integer to prevent timeouts
        while (total_bytes_written < content_length) {
            size_t remaining = content_length - total_bytes_written;
            size_t read_size = std::min(buffer.size(), remaining);
            
            ssize_t bytes_received = recv(socket_fd, buffer.data(), read_size, 0);
            if (bytes_received <= 0) break;
            
            fwrite(buffer.data(), bytes_received, 1, fp);
            fflush(fp);
            
            total_bytes_written += bytes_received;
        }

        body_consumed = true;
        fclose(fp); 
    }

    inline void pipe_body(int dest_fd) {
        read_body(dest_fd);
    }

// Yields chunks of data as string_views pointing directly into our buffer
    std::generator<std::string_view> stream_body() {
        size_t content_length = 0;
        if (malformed || !has_header("content-length")) {
            body_consumed = true;
            co_return; // Clean exit for coroutines
        }

        try {
            content_length = std::stoul(get_header("content-length"));
        } catch (...) {
            body_consumed = true;
            co_return;
        }

        if (content_length == 0 || (method != "POST" && method != "PUT" && method != "PATCH")) {
            body_consumed = true;
            co_return;
        }

        size_t total_bytes_yielded = 0;

        // 1. Yield leftover bytes currently sitting in the header buffer
        if (buffer_pos < buffer_size) {
            size_t bytes_available = buffer_size - buffer_pos;
            size_t bytes_to_copy = std::min(bytes_available, content_length);
            
            // Yield a non-owning slice pointing into our existing buffer
            co_yield std::string_view(buffer.data() + buffer_pos, bytes_to_copy);
            
            total_bytes_yielded += bytes_to_copy;
            buffer_pos += bytes_to_copy;
        }

        // 2. Yield upcoming chunks directly from the socket stream
        while (total_bytes_yielded < content_length) {
            size_t remaining = content_length - total_bytes_yielded;
            size_t read_size = std::min(buffer.size(), remaining);
            
            ssize_t bytes_received = recv(socket_fd, buffer.data(), read_size, 0);
            if (bytes_received <= 0) {
                break; // Network connection snapped early
            }
            
            co_yield std::string_view(buffer.data(), bytes_received);
            total_bytes_yielded += bytes_received;
        }

        body_consumed = true;
    }

};

#endif // __REQUEST_HPP__