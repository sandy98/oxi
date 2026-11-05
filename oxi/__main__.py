# -*- coding: utf-8 -*-

import sys
import os

def main():
    # 1. Determine the directory where this package is installed
    package_dir = os.path.dirname(os.path.abspath(__file__))
    cpp_binary_path = os.path.join(package_dir, "server")

    # 2. Route to the appropriate engine
    if "--julia" in sys.argv:
        # 🟣 JULIA MODE
        sys.argv.remove("--julia")
        
        import asyncio
        from .run_julia import main as julia_main
        try:
            asyncio.run(julia_main())
        except KeyboardInterrupt:
            pass

    elif "--python" in sys.argv:
        # 🐍 PYTHON MODE (Forced)
        sys.argv.remove("--python")
        from .server import main as server_main
        sys.argv[0] = "oxiserver"
        server_main()

    elif os.path.exists(cpp_binary_path) and os.access(cpp_binary_path, os.X_OK):
        # 🚀 C++ ENGINE FOUND
        sys.argv[0] = cpp_binary_path
        try:
            os.execv(cpp_binary_path, sys.argv)
        except OSError as e:
            print(f"Error executing C++ server: {e}")
            sys.exit(1)

    else:
        # 🐍 PYTHON MODE (Fallback)
        print("\033[36m[OxiServer]\033[0m C++ binary not found. Falling back to pure Python engine.")
        print("\033[36m[OxiServer]\033[0m To enable the C++ engine, run: oxibuild")
        print()
        
        from .server import main as server_main
        sys.argv[0] = "oxiserver"
        server_main()

if __name__ == "__main__":
    main()