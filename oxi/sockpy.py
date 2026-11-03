# sockpy.py
import asyncio
import socket
import os

visitor_count = 0

async def async_handle_client(fd):
    global visitor_count
    visitor_count += 1

    print(f"[Python Async Task] Handling socket descriptor: {fd} on the global loop.")
    
    # By using the socket constructor directly with the fileno, we wrap it.
    # To completely clean up both the wrapper and the original C++ descriptor number,
    # we will manually track and close the raw fd at the end.
    py_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, fileno=fd)
    py_socket.setblocking(False) 
    
    loop = asyncio.get_running_loop()
    try:
        response_content = f"Hello from OxiServer! You're visitor number: {visitor_count}\n"
        response = f"HTTP/1.1 200 OK\r\nContent-Length: {len(response_content)}\r\nConnection: close\r\n\r\n{response_content}".encode('utf-8')
        await loop.sock_sendall(py_socket, response)
    except Exception as e:
        print(f"[Python Async Task] Error on fd {fd}: {e}")
    finally:
        # Crucial step: closing py_socket clears Python's tracking, 
        # but to guarantee the C++ assigned slot is fully released to the OS:
        try:
            py_socket.close()
            # Force close the raw file descriptor slot if it's still open
            os.close(fd)
        except OSError:
            pass # Already closed safely
        print(f"[Python Async Task] Finished processing fd {fd} and fully released handles.")
