# oxi/rundemo.py
import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path

def main():
    # 1. Find where the oxi package is installed
    package_dir = Path(__file__).parent.resolve()
    demo_static_dir = package_dir / "apps" / "static"
    
    # 2. Find the C++ binary (if compiled)
    cpp_binary_path = package_dir / "server"
    is_cpp_compiled = cpp_binary_path.exists() and cpp_binary_path.stat().st_size > 4096

    # 3. Create a temporary workspace
    print("🚀 Preparing OxiServer demo workspace...")
    with tempfile.TemporaryDirectory(prefix="oxi_demo_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy the static assets into the temporary workspace
        if demo_static_dir.exists():
            print(f"📂 Copying demo assets to {temp_path}/static...")
            shutil.copytree(demo_static_dir, temp_path / "static")
        else:
            print("⚠️ Warning: Demo static assets not found in package.")
            
        # 4. Determine which engine to use
        if is_cpp_compiled:
            print("✅ Using compiled C++ engine.")
            cmd = [str(cpp_binary_path), "apps.demo:app"]
        else:
            print("🐍 C++ engine not compiled. Using pure Python engine.")
            print("   (Run 'oxibuild' to enable the 1.45 GB/sec C++ engine)")
            cmd = [sys.executable, str(package_dir / "server.py"), "apps.demo:app"]

        print(f"\n🌐 Starting server at http://localhost:8086")
        print(f"   Serving from temporary directory: {temp_path}")
        print(f"   Press Ctrl+C to stop.\n")

        try:
            # 5. Run the server with the temporary directory as CWD
            subprocess.run(cmd, cwd=temp_path, check=True)
        except KeyboardInterrupt:
            print("\n\n👋 Demo server stopped. Cleaning up...")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Demo server exited with error code {e.returncode}")
            sys.exit(1)

if __name__ == "__main__":
    main()