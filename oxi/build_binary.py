# oxi/build_binary.py
import subprocess
import sys
import os
import platform
import argparse

def check_cpp23(compiler):
    """Check if the compiler supports C++23."""
    try:
        code = "#include <generator>\nint main() { return 0; }"
        proc = subprocess.run(
            [compiler, "-std=c++23", "-x", "c++", "-", "-o", "/dev/null"],
            input=code, text=True, capture_output=True, check=False
        )
        return proc.returncode == 0
    except FileNotFoundError:
        return False

def find_compiler():
    """Find a C++23 compatible compiler."""
    print("🔍 Checking for a C++23 compatible compiler...")
    compilers = ["g++", "g++-14", "g++-13", "clang++", "clang++-18", "clang++-17"]
    
    for c in compilers:
        if check_cpp23(c):
            return c
            
    print("\n❌ No C++23 compatible compiler found.")
    print("OxiServer requires C++23 (specifically for <generator>).")
    
    if platform.system() == "Linux" and ("Ubuntu" in platform.version() or os.path.exists("/etc/lsb-release")):
        print("\n💡 On Ubuntu 22.04, you can install GCC 14 by running:")
        print("   sudo add-apt-repository ppa:ubuntu-toolchain-r/test")
        print("   sudo apt update")
        print("   sudo apt install g++-14")
        print("   sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-14 100")
    elif platform.system() == "Darwin":
        print("\n💡 On macOS, install the latest Xcode Command Line Tools:")
        print("   xcode-select --install")
    else:
        print("\n💡 Please install GCC 13+ or Clang 16+.")
    return None

def main():
    parser = argparse.ArgumentParser(
        prog="oxibuild",
        description="Compile or clean the OxiServer C++ engine."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="build",
        choices=["build", "clean"],
        help="Action to perform: 'build' (default) or 'clean'"
    )
    
    args = parser.parse_args()
    
    package_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 🚀 Handle the 'clean' action
    if args.action == "clean":
        print("🧹 Cleaning the C++ engine...")
        try:
            subprocess.run(["make", "clean"], cwd=package_dir, check=True)
            print("✅ Cleaned. The 'server' binary has been restored to the placeholder.")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Clean failed (Exit code {e.returncode}).")
            sys.exit(1)
        return

    # 🚀 Handle the 'build' action (default)
    compiler = find_compiler()
    if not compiler:
        sys.exit(1)
        
    print(f"✅ Found {compiler} with C++23 support.")
    print(f"🔨 Compiling server.cpp with {compiler} in {package_dir}...")
    
    env = os.environ.copy()
    env["CXX"] = compiler
    
    try:
        subprocess.run(["make"], cwd=package_dir, env=env, check=True)
        print(f"\n🚀 Success! The 'server' binary is ready at: {os.path.join(package_dir, 'server')}")
        print("   Run it from anywhere with: oxiserver apps.demo:app")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Compilation failed (Exit code {e.returncode}).")
        sys.exit(1)

if __name__ == "__main__":
    main()