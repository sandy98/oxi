# -*- coding: utf-8 -*-

import os
import sys
import asyncio

async def main():
    serverfile = os.path.join(os.path.dirname(__file__), "server.jl")
    
    if "--julia" in sys.argv: 
        sys.argv.remove("--julia")
        
    try:
        # Build the command: julia server.jl [app_target]
        cmd = ["julia", serverfile]
        if len(sys.argv) > 1:
            cmd.append(sys.argv[1])
            
        # Start the Julia process
        process = await asyncio.create_subprocess_exec(*cmd)
        
        # Wait for it to finish (optional, but ensures Ctrl+C propagates cleanly)
        await process.wait()
        
    except KeyboardInterrupt:
        print("\nOxiserver left the stage...")
        return
    except Exception as exc:
        excname = exc.__class__.__name__
        print(f"{excname}: {exc}")
        print("Leaving now")
        return

if __name__ == '__main__':
    asyncio.run(main())