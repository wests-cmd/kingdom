"""Owner-operated relay of signed inventories over existing pinned SSH access."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def api(host, path, payload=None):
    code = f'''import json,urllib.request,os
from pathlib import Path
os.chdir({host['cwd']!r})
body={payload!r}
request=urllib.request.Request('http://127.0.0.1:{int(host['port'])}'+{path!r},data=json.dumps(body).encode() if body is not None else None,headers={{'Authorization':'Bearer '+Path({host['token_file']!r}).read_text().strip(),'Content-Type':'application/json','X-Kingdom-Request':'1'}})
with urllib.request.urlopen(request,timeout=8) as response:print(response.read().decode())
'''
    completed = subprocess.run(host['ssh'] + [host.get('python', 'python3') + ' -'], input=code,
                               capture_output=True, text=True, encoding="utf-8", timeout=15)
    if completed.returncode: raise RuntimeError('Peer inventory transport failed; inspect host service status')
    return json.loads(completed.stdout)


def exchange(hosts):
    identities = [api(host, '/nodes/identity')['node_id'] for host in hosts]
    if identities[0] == identities[1]: raise ValueError('Distinct paired Kingdom identities required')
    for sender, receiver in [(0, 1), (1, 0)]:
        message = api(hosts[sender], '/federation/' + identities[receiver] + '/heartbeat-proof', {})
        result = api(hosts[receiver], '/nodes/rpc', message)
        if not result.get('ping', {}).get('success') or not result.get('inventory_proof'):
            raise ValueError('Signed inventory support or approval missing')
        accepted = api(hosts[sender], '/nodes/rpc', result['inventory_proof'])
        if not accepted.get('ping', {}).get('success'): raise ValueError('Inventory response rejected')
    return identities


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=int, default=15)
    args = parser.parse_args()
    if not 10 <= args.interval <= 30: parser.error('Use a 10–30 second inventory interval')
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    if len(config['hosts']) != 2: raise ValueError('Configure exactly two owner-authorized hosts')
    state_path = Path(config['state_file'])
    while True:
        start = time.monotonic()
        state = {'pid': os.getpid(), 'observed_at': time.time(), 'model_inference': False}
        try: state.update(status='synced', kingdoms=exchange(config['hosts']))
        except Exception as error: state.update(status='unavailable', error_class=type(error).__name__)
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2), encoding='utf-8'); temporary.replace(state_path)
        if not args.loop: return 0 if state['status'] == 'synced' else 1
        time.sleep(max(1, args.interval - (time.monotonic() - start)))


if __name__ == '__main__': raise SystemExit(main())
