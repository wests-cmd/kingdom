"""Explicit SSH service inventory; mutations become exact governed process tasks."""
import json
from pathlib import Path
import re
import subprocess
import shutil
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ServiceNode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100)
    mode: Literal['ssh','local'] = 'ssh'
    ssh_executable: str = ''
    destination: str = ''
    identity_file: str = ''
    units: list[str] = Field(min_length=1,max_length=30)

def validate(node):
    if node.mode=='local':
        if not shutil.which('systemctl'):raise ValueError('Local service control requires systemd')
    else:
        if not re.fullmatch(r'[a-z_][a-z0-9_-]*@[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}',node.destination):raise ValueError('Use a user@hostname SSH destination')
        for path in (node.ssh_executable,node.identity_file):
            if not Path(path).is_absolute() or not Path(path).is_file(): raise ValueError('Use installed SSH and key files by absolute path')
    if any(not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.@-]{0,120}\.service',unit) for unit in node.units):
        raise ValueError('Use explicit systemd service names')
    return node

class ServiceNodes:
    def __init__(self,engine,database):
        self.engine,self.db=engine,database
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS service_nodes(id TEXT PRIMARY KEY,config_json TEXT NOT NULL)');conn.commit()

    def list(self):
        with self.db.get_connection() as conn:
            return [{'id':row[0],**json.loads(row[1])} for row in conn.execute('SELECT id,config_json FROM service_nodes ORDER BY id')]

    def save(self,ident,node):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',ident): raise ValueError('Use a short node name')
        validate(node)
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO service_nodes VALUES(?,?) ON CONFLICT(id) DO UPDATE SET config_json=excluded.config_json',(ident,json.dumps(node.model_dump())));conn.commit()
        self.engine.events.publish('services.node_saved',{'id':ident})
        return {'id':ident,**node.model_dump()}

    def config(self,ident):
        found=next((item for item in self.list() if item['id']==ident),None)
        if not found: raise ValueError('Service node not found')
        return validate(ServiceNode.model_validate({k:v for k,v in found.items() if k!='id'}))

    @staticmethod
    def command(node,action,units):
        if node.mode=='local':
            import shlex
            return [shutil.which('systemctl'),'--user',*shlex.split(action),*units]
        # Units are validated and allowlisted, so remote shell parsing cannot introduce new commands.
        return [node.ssh_executable,'-i',node.identity_file,'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                '-o','ConnectTimeout=8',node.destination,'systemctl --user '+action+' '+' '.join(units)]

    def inspect(self,ident):
        node=self.config(ident)
        command=self.command(node,'show --property=Id,ActiveState,SubState,Description --no-pager',node.units)
        result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20,
                              **({'creationflags':subprocess.CREATE_NO_WINDOW} if __import__('os').name=='nt' else {}))
        if result.returncode: raise ValueError('SSH service inspection failed; check connectivity and the pinned host key')
        blocks=[]
        for raw in result.stdout[:64000].split('\n\n'):
            properties=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
            if properties.get('Id') in node.units: blocks.append(properties)
        return {'id':ident,'services':blocks,'scope':'Observed systemd user services. Registration does not migrate or replace their deployment.'}

    def action(self,ident,unit,action,*,requested_by_peer=None):
        node=self.config(ident)
        if unit not in node.units or action not in {'start','stop','restart'}: raise ValueError('Choose a registered service and supported action')
        argv=self.command(node,action,[unit])
        return self.engine.submit_task(f'{action} service {unit} on {ident}',{'actor':'owner','tool':'process.run@1.0.0',
            'tool_parameters':{'argv':argv,'timeout_seconds':60},'service_node':ident,'service_unit':unit,
            **({'requested_by_peer':requested_by_peer} if requested_by_peer else {}),
            'verification_scope':'Command exit only. Inspect service state afterward.'})
