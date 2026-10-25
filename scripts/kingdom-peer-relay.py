"""Owner-operated transport for signed Kingdom operations over existing SSH.

This connector grants no access, runs no model and never approves update tasks.
The configured endpoints create, execute and verify every signed operation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import os


def api(host,path,body=None,method=None):
    code=f'''import json,urllib.request,urllib.error,os
from pathlib import Path
os.chdir({host['cwd']!r})
body={body!r}
r=urllib.request.Request('http://127.0.0.1:{int(host['port'])}'+{path!r},method={method!r},data=json.dumps(body).encode() if body is not None else None,headers={{'Authorization':'Bearer '+Path({host['token_file']!r}).read_text().strip(),'Content-Type':'application/json','X-Kingdom-Request':'1'}})
try:
 with urllib.request.urlopen(r,timeout=90) as response:print(response.read().decode())
except urllib.error.HTTPError as e:print(json.dumps({{'http_error':e.code,'detail':e.read().decode()[:1000]}}))
'''
    result=subprocess.run(host['ssh']+[host.get('python','python3')+' -'],input=code,capture_output=True,text=True,encoding='utf-8',timeout=110,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise RuntimeError('Owner transport failed; no completion claimed')
    value=json.loads(result.stdout)
    if isinstance(value,dict) and 'http_error' in value:raise RuntimeError(json.dumps(value))
    return value


def identities(hosts):
    values=[api(host,'/nodes/identity')['node_id'] for host in hosts]
    if len(set(values))!=len(values):raise ValueError('Configure distinct Kingdom identities')
    return values


def sync(hosts,source,target,project,ids=None):
    peers=identities(hosts);request={'peer':peers[target],'project':project}
    if ids is not None:request['ids']=ids
    plan=api(hosts[source],'/vault-sync/export-batches',request)
    receipts=[]
    for batch in plan['batches']:
        prepared=api(hosts[source],'/vault-sync/prepare-proof',{**request,'ids':batch['ids']})
        response=api(hosts[target],'/nodes/rpc',prepared['proof'])
        receipts.append(api(hosts[source],'/vault-sync/accept-proof',{'peer':peers[target],'project':project,'expected_batch':prepared['batch'],'proof':response['proof']}))
    return {'status':'replicated','project':project,'batches':receipts,'source_retained':True}


def manage(hosts,source,target,operation,arguments):
    peers=identities(hosts)
    proof=api(hosts[source],'/knight-management/'+peers[target]+'/proof',{'operation':operation,'arguments':arguments})
    response=api(hosts[target],'/nodes/rpc',proof['message'])
    return api(hosts[source],'/knight-management/'+peers[target]+'/receipt',response)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--source',type=int,default=0);p.add_argument('--target',type=int,default=1)
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('sync');s.add_argument('--project',required=True)
    sub.add_parser('inspect')
    u=sub.add_parser('stage-update');u.add_argument('--archive',required=True)
    for command in ('activate-update','update-status'):
        u=sub.add_parser(command);u.add_argument('--release',required=True)
    a=p.parse_args();hosts=json.loads(Path(a.config).read_text(encoding='utf-8-sig'))['hosts']
    if a.source==a.target or not 0<=a.source<len(hosts) or not 0<=a.target<len(hosts):p.error('Select two different configured Knights')
    if a.command=='sync':result=sync(hosts,a.source,a.target,a.project)
    elif a.command=='stage-update':
        import base64,hashlib
        raw=Path(a.archive).read_bytes()
        if len(raw)>32*1024*1024:p.error('Source archive exceeds 32 MB')
        result=manage(hosts,a.source,a.target,'stage_update',{'archive_b64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()})
    else:result=manage(hosts,a.source,a.target,a.command.replace('-','_'),{} if a.command=='inspect' else {'release':a.release})
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
