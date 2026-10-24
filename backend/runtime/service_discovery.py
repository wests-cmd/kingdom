"""Bounded running/startup observation; no host escape or new grants."""
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import time
import stat
import re
import math
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


def read_host_container_report(path, *, now=None, owner_uid=0):
    """Consume an operator-installed report, never a Docker socket or host command.

    The production reader accepts only root-owned, non-group/world-writable
    regular files. Atomic replacement by the host observer keeps snapshots whole.
    """
    now=time.time() if now is None else now
    unavailable=validate_services({'state':'unavailable','scope':'container',
        'observation_source':'host_report','services':[], 'observed_at':now})
    try:
        path=Path(path)
        if not path.is_absolute() or path.resolve()!=path:
            return unavailable
        fd=os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=owner_uid
                    or info.st_mode & 0o022 or info.st_size>65536):
                return unavailable
            raw=stream.read(65537)
        if len(raw)>65536:
            return unavailable
        data=json.loads(raw)
        if not isinstance(data,dict) or type(data.get('version')) is not int or data['version']!=1:
            return unavailable
        observed=data.get('observed_at')
        if (type(observed) not in (int,float) or not math.isfinite(observed)
                or not 0<=now-observed<=60 or data.get('state')!='observed'):
            return unavailable
        containers=data.get('containers')
        if (not isinstance(containers,list) or len(containers)>128
                or type(data.get('truncated',False)) is not bool):
            return unavailable
        rows=[]
        for item in containers:
            if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',item['name']):
                return unavailable
            state={'running':'running','created':'stopped','exited':'stopped','dead':'stopped',
                   'paused':'unknown','restarting':'unknown','removing':'unknown'}.get(item.get('state'))
            if state is None:
                return unavailable
            restart=item.get('restart_policy','unknown')
            rows.append({'id':'docker:'+item['name'],'name':item['name'],'state':state,
                         'startup':'unknown','restart_policy':restart})
        return validate_services({'state':'observed','scope':'container','observation_source':'host_report',
            'services':rows,'observed_at':float(observed),'running_state':'observed',
            'startup_state':'unavailable','truncated':data.get('truncated',False)})
    except (OSError,ValueError,TypeError,AttributeError):
        return unavailable


def discover_local_services():
    system=platform.system()
    result={'state':'unsupported','services':[],'observed_at':time.time(),'scope':'unknown',
            'running_state':'unsupported','startup_state':'unsupported','truncated':False}
    if system=='Linux' and in_container():
        host_report=os.environ.get('KINGDOM_HOST_CONTAINER_REPORT')
        if host_report:
            return read_host_container_report(host_report)
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
