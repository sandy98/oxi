# oxi/scaffolding.py
import os
import sys
import argparse
from pathlib import Path

HTML_PREFIX = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>My Oxi App</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <nav>
        <a href="/">Home</a>
        <a href="/contents">Contents</a>
        <a href="/about">About</a>
    </nav>
    <main>
"""

HTML_SUFFIX = """    </main>
</body>
</html>
"""

def write_file(path: Path, content: str, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        path.chmod(0o755)
    print(f"  📄 Created {path}")

def main():
    parser = argparse.ArgumentParser(
        prog="scaffolding",
        description="Generate a new Oxi project structure."
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=".",
        help="Project directory name (default: current directory)"
    )
    parser.add_argument(
        "--with-demo",
        action="store_true",
        help="Include the demo app (demonstrates OxiApp mounting)"
    )
    
    args = parser.parse_args()
    target_dir = Path(args.name).resolve()
    
    print(f"\n🚀 Scaffolding new Oxi project: {target_dir}\n")

    # 1. Main App
    write_file(target_dir / "app.py", f'''# app.py
from oxi.app import OxiApp

app = OxiApp("My Oxi App")

HTML_PREFIX = """{HTML_PREFIX}"""
HTML_SUFFIX = """{HTML_SUFFIX}"""

@app.get("/")
async def home():
    return HTML_PREFIX + "<h1>Welcome to Oxi!</h1>" + HTML_SUFFIX

@app.get("/contents")
async def contents():
    return HTML_PREFIX + "<h1>Contents</h1><p>Your content here.</p>" + HTML_SUFFIX

@app.get("/about")
async def about():
    return HTML_PREFIX + "<h1>About</h1><p>Built with OxiServer.</p>" + HTML_SUFFIX
''')

    # 2. About (version metadata)
    write_file(target_dir / "__about__.py", '''# __about__.py
__version__ = "0.1.0"
__config__ = {
    "static_dir": "static",
    "cgi_dir": "cgi-bin",
    "index_files": ["index.html"],
    "allow_dirlisting": True,
    "allow_cgi": True,
}
''')

    # 3. Static assets
    write_file(target_dir / "static" / "index.html", 
               f"{HTML_PREFIX}<h1>Static Homepage</h1>{HTML_SUFFIX}")
    write_file(target_dir / "static" / "style.css", """body { font-family: sans-serif; margin: 2rem; }
nav a { margin-right: 1rem; text-decoration: none; color: #2563eb; }
""")

    # 4. Demo app (optional)
    if args.with_demo:
        write_file(target_dir / "apps" / "demo.py", '''# apps/demo.py
from oxi.app import OxiApp

app = OxiApp("Demo")

@app.get("/")
async def index():
    return "<h1>Hello from the demo app!</h1><p>Mounted at /demo</p>"
''')
        
        # Update app.py to mount the demo
        app_content = (target_dir / "app.py").read_text()
        app_content += '''
# Mount the demo app at /demo
from apps.demo import app as demoapp
app.mount(demoapp, "/demo", "/")
'''
        (target_dir / "app.py").write_text(app_content)
        print(f"  🔗 Updated {target_dir / 'app.py'} to mount the demo at /demo")

    # 5. Instructions
    print(f"""
\n✅ Project generated successfully!

To start your new Oxi project:

    cd {args.name}
    oxiserver app:app

Then open http://localhost:8086 in your browser.
""")

if __name__ == "__main__":
    main()