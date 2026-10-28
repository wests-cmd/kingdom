"""User-login companion supervisor. No shell, credentials or execution RPCs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    root=Path(__file__).resolve().parent
    lock=(root/'supervisor.lock').open('a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0)
        if not lock.read(1):lock.write(b'1');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
    children={}
    try:
        while True:
            state={'observed_at':time.time(),'pid':os.getpid(),'peers':{}}
            names = ['laptop2','laptop3','dt1']
            if (root/'listener.json').is_file():
                names.append('listener')
            for name in names:
                child=children.get(name)
                if child is None or child.poll() is not None:
                    child=subprocess.Popen([sys.executable,str(root/'link.py'),'--config',str(root/(name+'.json'))],
                                           cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    children[name]=child
                state['peers'][name]={'pid':child.pid,'running':child.poll() is None}
            temporary=root/'supervisor-state.tmp'
            temporary.write_text(json.dumps(state))
            temporary.replace(root/'supervisor-state.json')
            time.sleep(8)
    finally:
        for child in children.values():
            if child.poll() is None:child.terminate()
        lock.close()


if __name__=='__main__':main()
