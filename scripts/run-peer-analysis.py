"""Relay only reviewed pure analysis between existing paired computers over pinned SSH.

Config contains controller/worker host dictionaries (ssh,cwd,port,token_file), plus
worker.python and worker.source_root. Never pairs computers or grants capabilities.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

ALLOWED_TOOLS = {'text.analyze@1.0.0', 'code.python.analyze@1.0.0'}


def validate_task(task, worker_id):
    if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not task['id']:
        raise ValueError('Missing task identity')
    meta = task.get('metadata', {})
    if meta.get('tool') not in ALLOWED_TOOLS or meta.get('capability', 'compute') != 'compute':
        raise ValueError('Only native compute analysis is supported')
    if meta.get('execution_target') != 'remote' or (task.get('assigned_knight') or meta.get('assigned_knight')) != worker_id:
        raise ValueError('Task is not assigned to this computer')
    if str(task.get('status', '')).lower() != 'leased' or not isinstance(task.get('lease_id'), str) or not task['lease_id']:
        raise ValueError('An exact active lease is required')
    if type(task.get('fencing_token')) is not int or task['fencing_token'] < 1:
        raise ValueError('Invalid fencing token')
    params = meta.get('tool_parameters', {'text': task.get('prompt')})
    if not isinstance(params, dict) or set(params) != {'text'} or not isinstance(params['text'], str):
        raise ValueError('Only literal supplied text is accepted')
    if len(params['text'].encode()) > 2_000_000:
        raise ValueError('Analysis input is too large')
    return task


def worker_operation(request):
    # load_from_file deliberately fails if no existing identity; never creates one.
    from backend.cluster.identity import KingdomIdentity
    from backend.cluster.transport import RPCSecureTransport
    identity = KingdomIdentity.load_from_file('data/identities/kingdom_identity.json')
    if identity is None or identity.node_id != request['worker_id']:
        raise ValueError('Existing worker identity mismatch')
    transport = RPCSecureTransport(identity)
    if request['operation'] == 'poll':
        return transport.create_signed_message(request['controller_id'], 'task_poll', {'node_id': identity.node_id, 'supported_tools': sorted(ALLOWED_TOOLS)})
    if request['operation'] != 'execute':
        raise ValueError('Unsupported relay operation')
    task = validate_task(request['task'], identity.node_id)
    from backend.runtime.execution import execute_request, verify_request_result
    try:
        output = execute_request(task, ['compute'])
        verification = verify_request_result(task, output, allow_local_model=False)
        if verification.get('state') != 'VERIFIED':
            raise ValueError('Worker verification failed')
        payload = {'status':'completed', 'output':output}
    except Exception as error:
        payload = {'status':'failed', 'error':type(error).__name__}
    payload.update(task_id=task['id'], executed_by=identity.node_id,
                   lease_id=task['lease_id'], fencing_token=task['fencing_token'])
    return transport.create_signed_message(request['controller_id'], 'task_result', payload)


def remote_worker(host, request):
    source = Path(__file__).read_text(encoding='utf-8-sig')
    code = (f'import os,sys,json;os.chdir({host["cwd"]!r});sys.path.insert(0,{host["source_root"]!r})\n'
            + 'scope={"__name__":"peer_analysis_worker"}\n'
            + f'exec(compile({source!r},"peer-analysis-worker","exec"),scope)\n'
            + f'print(json.dumps(scope["worker_operation"]({request!r})))\n')
    completed = subprocess.run(host['ssh'] + [host['python'] + ' -'], input=code,
                               text=True,encoding="utf-8",capture_output=True,timeout=45)
    if completed.returncode:
        raise RuntimeError('Pinned worker execution failed; inspect the worker service')
    return json.loads(completed.stdout)


def inventory_api():
    spec = importlib.util.spec_from_file_location('peer_inventory',Path(__file__).with_name('sync-peer-inventories.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.api


def relay_once(config, api=None, worker=None):
    api = api or inventory_api(); worker = worker or remote_worker
    controller, executor = config['controller'], config['worker']
    identities=[]
    for host in (controller,executor):
        identity=api(host,'/nodes/identity')
        expected=host.get('expected_identity')
        if expected and any(identity.get(key)!=value for key,value in expected.items()):
            raise ValueError('Pinned Kingdom identity changed; no task polled')
        identities.append(identity['node_id'])
    controller_id,worker_id=identities
    if controller_id == worker_id:
        raise ValueError('Distinct installed identities are required')
    base = {'controller_id':controller_id,'worker_id':worker_id}
    poll = worker(executor,{**base,'operation':'poll'})
    reply = api(controller,'/nodes/rpc',poll)
    tasks = reply.get('tasks')
    if reply.get('status') != 'ok' or not isinstance(tasks,list) or len(tasks)>1:
        raise ValueError('Unexpected task poll response')
    if not tasks:
        return {'status':'idle','worker_id':worker_id}
    task = validate_task(tasks[0],worker_id)
    current = api(controller,'/tasks/'+task['id'])
    validate_task(current,worker_id)
    if any(current.get(key) != task.get(key) for key in ('id','lease_id','fencing_token','metadata','prompt')):
        raise ValueError('Task or lease changed before execution')
    result = worker(executor,{**base,'operation':'execute','task':task})
    if (result.get('sender_id') != worker_id or result.get('target_id') != controller_id
            or result.get('msg_type') != 'task_result'):
        raise ValueError('Result identity mismatch')
    payload = result.get('payload',{})
    if any(payload.get(key) != value for key,value in {
            'task_id':task['id'],'executed_by':worker_id,
            'lease_id':task['lease_id'],'fencing_token':task['fencing_token']}.items()):
        raise ValueError('Result lease mismatch')
    accepted = api(controller,'/nodes/rpc',result)
    if payload.get('status') == 'failed':
        if accepted.get('failed',{}).get('id') != task['id']:
            raise ValueError('Failure was not recorded')
        return {'status':'failed','task_id':task['id'],'worker_id':worker_id}
    completed = accepted.get('completed',{})
    receipt = completed.get('result',{})
    if (completed.get('id') != task['id'] or str(completed.get('status')).lower() != 'completed'
            or receipt.get('executed_by') != worker_id
            or receipt.get('verification',{}).get('state') != 'VERIFIED'):
        raise ValueError('Controller did not independently verify completion')
    return {'status':'verified','task_id':task['id'],'worker_id':worker_id,
            'tool':task['metadata']['tool'],'verification':receipt['verification']['state']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--once',action='store_true');mode.add_argument('--loop',action='store_true')
    parser.add_argument('--interval',type=int,default=10)
    args=parser.parse_args()
    if not 5 <= args.interval <= 60: parser.error('Use a 5–60 second interval')
    config=json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    state_path=Path(config['state_file']);last_receipt=None
    lock=state_path.with_suffix('.lock').open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:return 0
    if state_path.exists():
        try:last_receipt=json.loads(state_path.read_text(encoding='utf-8')).get('last_receipt')
        except (ValueError,OSError):pass
    while True:
        state={'pid':os.getpid(),'observed_at':time.time(),'model_inference':False}
        try:
            result=relay_once(config);state.update(result)
            if result['status'] != 'idle':last_receipt=result
        except Exception as error:state.update(status='unavailable',error_class=type(error).__name__)
        state['last_receipt']=last_receipt
        temporary=state_path.with_suffix('.tmp');temporary.write_text(json.dumps(state,indent=2),encoding='utf-8');temporary.replace(state_path)
        if not args.loop:
            print(json.dumps(state));return 0 if state['status'] in {'idle','verified'} else 1
        time.sleep(args.interval)


if __name__=='__main__':raise SystemExit(main())
