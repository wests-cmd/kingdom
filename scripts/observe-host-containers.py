"""Operator-owned, read-only container observer; never run inside an Apprentice.

Only names, runtime states and restart policy are exported. No environment,
mounts, logs, prompts, credentials, Docker socket or control API is shared.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time


def collect():
    result={'version':1,'state':'unavailable','observed_at':time.time(),'containers':[],'truncated':False}
    try:
        names=subprocess.run(['/usr/bin/docker','ps','-a','--format','{{.Names}}'],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=7,check=True).stdout
        if len(names)>65536:
            return result
        names=sorted(name for name in names.splitlines()
            if name.startswith('kingdom') and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name))
        result['truncated']=len(names)>128
        if names:
            # Docker formats only these selected fields, not full inspect output.
            template='{"name":{{json .Name}},"state":{{json .State.Status}},"restart_policy":{{json .HostConfig.RestartPolicy.Name}}}'
            raw=subprocess.run(['/usr/bin/docker','inspect','--format',template,*names[:128]],
                stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=7,check=True).stdout
            if len(raw)>65536:
                return result
            rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
            if len(rows)!=len(names[:128]):
                return result
            result['containers']=[{'name':row['name'].removeprefix('/'),
                'state':row['state'],'restart_policy':row['restart_policy']} for row in rows]
        result.update(state='observed',observed_at=time.time())
    except (OSError,subprocess.SubprocessError,ValueError,KeyError,TypeError,AttributeError):
        result.update(state='unavailable',containers=[])
    return result


def publish(target, report):
    target=Path(target)
    target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report),encoding='utf-8')
    temporary.chmod(0o644)
    temporary.replace(target)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/run/kingdom-host-observation/containers.json')
    parser.add_argument('--once',action='store_true')
    options=parser.parse_args()
    while True:
        publish(options.output,collect())
        if options.once:
            break
        time.sleep(15)
