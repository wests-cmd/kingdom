"""Bounded running/startup observation; no host escape or new grants."""
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import time
from backend.memory.portable_vault import clean_text
from backend.runtime.service_inventory import validate_services


def in_container():
    return Path('/.dockerenv').is_file() or Path('/run/.containerenv').is_file()


def read_rows(argv):
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=3,
                              **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        if result.returncode or len(result.stdout)>1024*1024:return None
        values=json.loads(result.stdout or '[]');values=[values] if isinstance(values,dict) else values
        return values if isinstance(values,list) and all(isinstance(value,dict) for value in values) else None
    except (OSError,subprocess.SubprocessError,ValueError,TypeError,AttributeError):
        return None


def label(value):
    if not isinstance(value,str) or not 1<=len(value)<=160 or any(ord(char)<32 for char in value):return None
    return clean_text(value)


def discover_local_services():
    system=platform.system()
    result={'state':'unsupported','services':[],'observed_at':time.time(),'scope':'unknown',
            'running_state':'unsupported','startup_state':'unsupported','truncated':False}
    if system=='Linux' and in_container():
        return validate_services({**result,'scope':'container'})
    if system=='Linux' and shutil.which('systemctl'):
        manager=shutil.which('systemctl')
        running=read_rows([manager,'--user','list-units','--type=service','--state=running','--output=json','--no-pager'])
        startup=read_rows([manager,'--user','list-unit-files','--type=service','--output=json','--no-pager'])
        result.update(scope='user_services',running_state='observed' if running is not None else 'unavailable',
                      startup_state='observed' if startup is not None else 'unavailable')
        rows={}
        for value in running or []:
            ident=label(value.get('unit'))
            if ident:rows[ident]={'id':ident,'name':label(value.get('description')) or ident,'state':'running','startup':'unknown'}
        for value in startup or []:
            ident=label(value.get('unit_file'))
            if not ident:continue
            state=value.get('state')
            mode=('enabled' if state in {'enabled','enabled-runtime'} else 'disabled' if state in {'disabled','masked','masked-runtime'}
                  else 'manual' if state in {'static','indirect','generated','transient'} else 'unknown')
            if ident in rows or mode=='enabled':
                rows.setdefault(ident,{'id':ident,'name':ident,'state':'stopped' if running is not None else 'unknown','startup':'unknown'})
                rows[ident]['startup']=mode
        values=list(rows.values())
        result['state']='observed' if running is not None or startup is not None else 'unavailable'
    elif system=='Windows' and shutil.which('powershell.exe'):
        values=read_rows([shutil.which('powershell.exe'),'-NoProfile','-NonInteractive','-Command',
                          'Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode | ConvertTo-Json -Compress'])
        result.update(scope='windows_services',state='observed' if values is not None else 'unavailable',
                      running_state='observed' if values is not None else 'unavailable',startup_state='observed' if values is not None else 'unavailable')
        rows=[]
        for value in values or []:
            ident=label(value.get('Name'))
            if not ident or (value.get('State')!='Running' and value.get('StartMode')!='Auto'):continue
            state='running' if value.get('State')=='Running' else 'stopped' if value.get('State')=='Stopped' else 'unknown'
            startup={'Auto':'enabled','Manual':'manual','Disabled':'disabled'}.get(value.get('StartMode'),'unknown')
            rows.append({'id':ident,'name':label(value.get('DisplayName')) or ident,'state':state,'startup':startup})
        values=rows
    else:return validate_services(result)
    values.sort(key=lambda row:(row['state']!='running',row['startup']!='enabled',row['id']))
    result.update(services=values[:128],truncated=len(values)>128)
    return validate_services(result)
