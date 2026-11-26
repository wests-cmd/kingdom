"""Experimental input adapter restricted to an explicitly enabled private Xvfb session.

Never attach to the normal host desktop, Wayland, or a remote display.
The launcher is responsible for the actual OS/container isolation.
"""
import os
from pathlib import Path
import shutil
import subprocess
import time

KEYS={'enter':'Return','tab':'Tab','escape':'Escape','backspace':'BackSpace',
      'ctrl+a':'ctrl+a','ctrl+c':'ctrl+c','ctrl+v':'ctrl+v','ctrl+s':'ctrl+s','ctrl+z':'ctrl+z'}


def available():
    return (os.name=='posix' and os.environ.get('KINGDOM_PRIVATE_X11_INPUT')=='1'
            and os.environ.get('DISPLAY')==':99' and not os.environ.get('WAYLAND_DISPLAY')
            and Path('/.dockerenv').is_file() and hasattr(os,'geteuid') and os.geteuid()!=0
            and bool(shutil.which('xdotool')))


def command(*args):
    executable=shutil.which('xdotool')
    if not executable:raise RuntimeError('Private X11 input tool missing')
    result=subprocess.run([executable,*args],check=True,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,timeout=5,shell=False)
    if len(result.stdout)>4096:raise ValueError('Unexpected private display response')
    return result.stdout.decode('utf-8').rstrip('\r\n')


def observe(title):
    if not available():raise PermissionError('Private X11 session not enabled')
    handle=int(command('getwindowfocus'))
    actual=command('getwindowname',str(handle))
    if not handle or actual!=title or int(command('getwindowfocus'))!=handle:
        raise PermissionError('Private foreground window changed')
    return {'ok':True,'window_title':title,'window_handle':handle,'observed_at':time.time(),
            'controls':[],'observation_scope':'private_x11_identity_only','input_supported':True}


def execute(params):
    if not available():raise PermissionError('Private X11 session not enabled')
    handle=params.get('window_handle')
    stamp=params.get('observed_at')
    title=params.get('window_title')
    if type(handle) is not int or type(stamp) not in (int,float) or not 0<=time.time()-stamp<=30:
        raise PermissionError('Fresh exact window observation required')
    def focused():
        if observe(title)['window_handle']!=handle:raise PermissionError('Private window changed')
    focused()
    if params.get('action')=='type_text':
        text=params.get('text')
        if not isinstance(text,str) or not 1<=len(text)<=256 or any(not 32<=ord(c)<127 for c in text):
            raise ValueError('Private X11 input accepts 1–256 printable ASCII characters')
        command('type','--clearmodifiers','--delay','8','--',text)
    elif params.get('action')=='key' and params.get('key') in KEYS:
        command('key','--clearmodifiers',KEYS[params['key']])
    else:raise ValueError('Private X11 currently supports reviewed text and key input only')
    focused()
    return {'action':params['action'],'window_title':title,'input_sent':True,
            'scope':'Private X11 input sent; independent application confirmation still required'}
