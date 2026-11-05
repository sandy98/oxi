# -*- coding: utf-8 -*-

import sys
import os

def is_real_binary(path):
    """Check if the file at path is the real compiled binary, not the stub."""
    if not os.path.exists(path):
        return False
    
    # The real binary is an ELF/Mach-O executable (large). The stub is a tiny text file.
    # A simple size check is the most robust cross-platform way.
    try:
        size = os.path.getsize(path)
        return size > 4096  # Stub is ~500 bytes, real binary is megabytes
    except OSError:
        return False

def main():
    package_dir = os.path.dirname(os.path.abspath(__file__))
    cpp_binary_path = os.path.join(package_dir, "server")

    if "--julia" in sys.argv:
        sys.argv.remove("--julia")
        import asyncio
        from .run_julia import main as julia_main
        try:
            asyncio.run(julia_main())
        except KeyboardInterrupt:
            pass

    elif "--python" in sys.argv:
        sys.argv.remove("--python")
        from .server import main as server_main
        sys.argv[0] = "oxiserver"
        server_main()

    elif is_real_binary(cpp_binary_path):
        # 🚀 Real C++ Engine found
        sys.argv[0] = cpp_binary_path
        try:
            os.execv(cpp_binary_path, sys.argv)
        except OSError as e:
            print(f"Error executing C++ server: {e}")
            sys.exit(1)

    else:
        # 🐍 Fallback to Python
        if os.path.exists(cpp_binary_path):
            print("\033[33m[OxiServer]\033[0m C++ binary placeholder found (not compiled).")
            print("\033[33m[OxiServer]\033[0m To enable the C++ engine, run: oxibuild\n")
        else:
            print("\033[33m[OxiServer]\033[0m C++ binary not found. Falling back to pure Python engine.\n")
        
        from .server import main as server_main
        sys.argv[0] = "oxiserver"
        server_main()

if __name__ == "__main__":
    main()