"""Read-only service observation. Discovery never grants management authority."""
import json
import os
import platform
import shutil
import subprocess
import time


def discover_local_services():
    system=platform.system()
    if system=='Linux' and shutil.which('systemctl'):
        argv=[shutil.which('systemctl'),'--user','list-units','--type=service','--state=running','--output=json','--no-pager']
    elif system=='Windows' and shutil.which('powershell.exe'):
        argv=[shutil.which('powershell.exe'),'-NoProfile','-NonInteractive','-Command',
              'Get-Service | Where-Object Status -eq Running | Select-Object Name,DisplayName | ConvertTo-Json -Compress']
    else:
        return {'state':'unsupported','services':[],'observed_at':time.time()}
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=6,
                              **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        if result.returncode or len(result.stdout)>1024*1024:raise ValueError('Service observation unavailable')
        values=json.loads(result.stdout or '[]');values=[values] if isinstance(values,dict) else values
        rows=[]
        for value in values[:128]:
            ident=value.get('unit') if system=='Linux' else value.get('Name')
            label=value.get('description') if system=='Linux' else value.get('DisplayName')
            if not isinstance(ident,str) or not 1<=len(ident)<=160 or any(ord(c)<32 for c in ident):continue
            label=label if isinstance(label,str) and not any(ord(c)<32 for c in label) else ident
            rows.append({'id':ident,'name':label[:160],'state':'running'})
        return {'state':'observed','services':rows,'observed_at':time.time(),'truncated':len(values)>128}
    except (OSError,subprocess.SubprocessError,ValueError,TypeError,AttributeError):
        return {'state':'unavailable','services':[],'observed_at':time.time()}
