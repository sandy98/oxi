# oxi/build_binary.py
import subprocess
import sys
import os
import platform

def check_cpp23(compiler):
    """Check if the compiler supports C++23."""
    try:
        # Test with a small C++23-only snippet (requires <generator> or <expected>)
        code = "#include <generator>\nint main() { return 0; }"
        proc = subprocess.run(
            [compiler, "-std=c++23", "-x", "c++", "-", "-o", "/dev/null"],
            input=code, text=True, capture_output=True, check=False
        )
        return proc.returncode == 0
    except FileNotFoundError:
        return False

def main():
    print("🔍 Checking for a C++23 compatible compiler...")
    
    # 1. Try standard names
    compilers = ["g++", "g++-14", "g++-13", "clang++", "clang++-18", "clang++-17"]
    valid_compiler = None
    
    for c in compilers:
        if check_cpp23(c):
            valid_compiler = c
            break
            
    if not valid_compiler:
        print("\n❌ No C++23 compatible compiler found.")
        print("OxiServer requires C++23 (specifically for <generator>).")
        
        if platform.system() == "Linux" and "Ubuntu" in platform.version() or os.path.exists("/etc/lsb-release"):
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
        sys.exit(1)
        
    print(f"✅ Found {valid_compiler} with C++23 support.")
    package_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Build
    print(f"🔨 Compiling server.cpp with {valid_compiler} in {package_dir}...")
    env = os.environ.copy()
    env["CXX"] = valid_compiler
    
    try:
        subprocess.run(["make"], cwd=package_dir, env=env, check=True)
        print("\n🚀 Success! The 'server' binary is ready.")
        print("   Run it with: oxiserver apps.demo:app")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Compilation failed (Exit code {e.returncode}).")
        sys.exit(1)

if __name__ == "__main__":
    main()