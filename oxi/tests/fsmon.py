# -- coding: utf-8 -*-

from pathlib import Path
import os
import time
import hashlib

def fs_monitor():

    print("Starting file system monitor...")
    parentdir = Path(__file__).parent

    pyfiles = [open(str(entry), 'rb') for entry in parentdir.glob("*.py")]
    hashes = [hashlib.sha1(fd.read()).hexdigest() for fd in pyfiles]


    # print(f"Watching {len(pyfiles)} files for changes.")

    while True:
        time.sleep(1)
        newpyfiles = [open(str(entry), 'rb') for entry in parentdir.glob("*.py")]
        if len(newpyfiles) != len(pyfiles):
            print(f"File count changed. Signaling server restart")
            time.sleep(0.5)  # Optional debounce
            os.execv(os.sys.executable, [os.sys.executable] + os.sys.argv)            # os.kill(os.getpid(), signal.SIGUSR1)
            # os.kill(os.getpid(), signal.SIGUSR1)
            # return
        newhashes = [hashlib.sha1(fd.read()).hexdigest() for fd in newpyfiles]
        if newhashes != hashes:
            print(f"File hashes changed. Signaling server restart")
            time.sleep(0.5)  # Optional debounce
            os.execv(os.sys.executable, [os.sys.executable] + os.sys.argv)            # os.kill(os.getpid(), signal.SIGUSR1)
            # os.kill(os.getpid(), signal.SIGUSR1)
            # return
        else:
            for fd in newpyfiles:
                fd.close()

#

if __name__ == "__main__":
    fs_monitor()