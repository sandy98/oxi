# -*- coding: utf-8 -*-

import sys, asyncio
from pathlib import Path

filepath = Path(__file__)
# print(str(filepath))
parentpath = filepath.parent
# print(str(parentpath))
grandparentpath = parentpath.parent
# print(str(grandparentpath))
sys.path.insert(0, str(parentpath))
sys.path.insert(0, str(grandparentpath))

if __name__ == "__main__" and not __package__:
    __package__ = "oxi"
    

try:
    if not "--julia" in sys.argv:
        from .server import main as static_main
        static_main()
    else:
        from .run_julia import main as static_main    
        asyncio.run(static_main())
except Exception as exc:
    excname = exc.__class__.__name__
    print(f"{excname}: {str(exc)}")
    raise


