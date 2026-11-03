# -*- coding: utf-8 -*-

import os, sys, asyncio
from pathlib import Path

filepath = Path(__file__)
# print(str(filepath))
parentpath = filepath.parent
# print(str(parentpath))
grandparentpath = parentpath.parent
# print(str(grandparentpath))
#examples_virtual_env_path = f"{parentpath}{os.path.sep}.examples-virtual-env/lib/python3.10/site-packages"
options_virtual_env_path = f"{parentpath}{os.path.sep}.options-virtual-env/lib/python3.10/site-packages"

# if Path(examples_virtual_env_path).is_dir():
#     sys.path.insert(0, str(examples_virtual_env_path))
if Path(options_virtual_env_path).is_dir():
    sys.path.insert(0, str(options_virtual_env_path))
    sys.executable = f"{options_virtual_env_path.replace('lib/python3.10/site-packages', 'bin/python3')}"
sys.path.insert(0, str(parentpath))
sys.path.insert(0, str(grandparentpath))

# import uvloop
# uvloop.install()
# from juliacall import Main as julia

async def main():
    serverfile = f"{os.path.dirname(__file__)}{os.path.sep}server.jl"
    if "--julia" in sys.argv: 
        sys.argv.remove("--julia")
    try:
        # julia.include("server.jl")
        if len(sys.argv) < 2:
            process = await asyncio.create_subprocess_exec("julia", serverfile)
        elif len(sys.argv) == 2:    
            process = await asyncio.create_subprocess_exec("julia", serverfile, sys.argv[1])
        else:
            process = await asyncio.create_subprocess_exec("julia", serverfile, sys.argv[1], sys.argv[2])
        # julia.OxiServer.run_server(appname)
        # while True:
        #     time.sleep(1)
    except KeyboardInterrupt:
        print("Oxiserver left the stage...")
        return
    except Exception as exc:
        excname = exc.__class__.__name__
        print(f"{excname}: {exc}")
        print("Leaving now")
        return

if __name__ == '__main__':
    asyncio.run(main())