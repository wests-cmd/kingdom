import importlib.util
from pathlib import Path
from copy import deepcopy
import pytest

spec=importlib.util.spec_from_file_location('peer_analysis',Path(__file__).parents[1]/'scripts/run-peer-analysis.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


def task():
    return {'id':'job','status':'leased','lease_id':'lease-exact','fencing_token':3,
            'assigned_knight':'worker','prompt':'source',
            'metadata':{'tool':'code.python.analyze@1.0.0','tool_parameters':{'text':'def f(): pass'},
                        'execution_target':'remote','capability':'compute'}}


@pytest.mark.parametrize('patch',[
    {'fencing_token':True},{'fencing_token':0},{'lease_id':''},{'status':'completed'},
    {'assigned_knight':'someone-else'},
    {'metadata':{'tool':'process.run@1.0.0'}}, {'metadata':{}},
    {'metadata':{'tool':'text.analyze@1.0.0','execution_target':'remote','tool_parameters':{'text':'x','argv':['bad']}}}])
def test_worker_rejects_unreviewed_tools_and_invalid_lease(patch):
    candidate=task();candidate.update(patch)
    with pytest.raises(ValueError):relay.validate_task(candidate,'worker')


@pytest.mark.parametrize('tool',['text.analyze@1.0.0','code.python.analyze@1.0.0'])
def test_native_worker_actually_executes_and_recomputes(monkeypatch,tool):
    from backend.cluster.identity import KingdomIdentity
    identity=KingdomIdentity('worker')
    monkeypatch.setattr(KingdomIdentity,'load_from_file',classmethod(lambda cls,path:identity))
    candidate=task();candidate['metadata']['tool']=tool
    request={'operation':'execute','task':candidate,'worker_id':'worker','controller_id':'controller'}
    response=relay.worker_operation(request)
    assert response['sender_id']=='worker' and response['target_id']=='controller'
    assert response['payload']['status']=='completed'
    assert response['payload']['fencing_token']==3
    assert response['payload']['output']['tool']==tool
    assert response['signature']


def test_worker_does_not_create_identity(monkeypatch):
    from backend.cluster.identity import KingdomIdentity
    monkeypatch.setattr(KingdomIdentity,'load_from_file',classmethod(lambda cls,path:None))
    with pytest.raises(ValueError,match='identity mismatch'):
        relay.worker_operation({'worker_id':'worker','operation':'poll','controller_id':'controller'})


def harness(idle=False,mutate=None):
    calls=[]
    def api(host,path,payload=None):
        if path=='/nodes/identity':return {'node_id':host['id']}
        if path=='/tasks/job':return task()
        if payload['msg_type']=='task_poll':return {'status':'ok','tasks':[] if idle else [task()]}
        return {'completed':{'id':'job','status':'completed','result':{
            'executed_by':'worker','verification':{'state':'VERIFIED'}}}}
    def worker(host,request):
        calls.append(request['operation'])
        if request['operation']=='poll':return {'msg_type':'task_poll'}
        result={'sender_id':'worker','target_id':'controller','msg_type':'task_result',
                'payload':{'task_id':'job','executed_by':'worker','lease_id':'lease-exact','fencing_token':3,'status':'completed'}}
        if mutate:mutate(result)
        return result
    return {'controller':{'id':'controller'},'worker':{'id':'worker'}},api,worker,calls


def test_idle_poll_does_not_execute():
    config,api,worker,calls=harness(idle=True)
    assert relay.relay_once(config,api,worker)['status']=='idle'
    assert calls==['poll']


@pytest.mark.parametrize('host',['controller','worker'])
def test_changed_pinned_identity_cannot_poll_or_execute(host):
    config,api,worker,calls=harness()
    config[host]['expected_identity']={'node_id':config[host]['id'],'fingerprint':'expected-key'}
    with pytest.raises(ValueError,match='Pinned Kingdom identity changed'):
        relay.relay_once(config,api,worker)
    assert calls==[]


def test_relay_requires_controller_verified_receipt():
    config,api,worker,calls=harness()
    assert relay.relay_once(config,api,worker)['status']=='verified'
    def bad_api(host,path,payload=None):
        result=api(host,path,payload)
        if 'completed' in result:result['completed']['result']['verification']['state']='UNVERIFIED'
        return result
    with pytest.raises(ValueError,match='independently verify'):
        relay.relay_once(config,bad_api,worker)


@pytest.mark.parametrize('mutate',[
    lambda value:value.update(sender_id='intruder'),
    lambda value:value['payload'].update(fencing_token=4),
    lambda value:value['payload'].update(lease_id='old-lease')])
def test_wrong_executor_or_fence_cannot_be_submitted(mutate):
    config,api,worker,calls=harness(mutate=mutate)
    with pytest.raises(ValueError):relay.relay_once(config,api,worker)


@pytest.mark.parametrize('supported',[[],['process.run@1.0.0'],['text.analyze@1.0.0']*2,'text.analyze@1.0.0',[None]])
def test_poll_rejects_invalid_supported_tool_filters(monkeypatch,supported):
    from types import SimpleNamespace
    from fastapi import HTTPException
    import backend.api as api
    monkeypatch.setattr(api.RPCSecureTransport,'verify_and_unwrap_message',lambda *a,**kw:{
        'valid':True,'sender_id':'worker','msg_type':'task_poll','payload':{'supported_tools':supported}})
    with pytest.raises(HTTPException) as error:
        api.handle_cluster_rpc(SimpleNamespace(model_dump=lambda:{}))
    assert error.value.status_code==400


def test_poll_skips_unsupported_job_before_leasing_and_selects_later_analysis(monkeypatch,tmp_path):
    from types import SimpleNamespace
    import backend.api as api
    from backend.runtime.tasks import TaskManager
    from backend.storage.repository import TaskRepository
    from backend.storage.db import Database
    manager=TaskManager(TaskRepository(Database(tmp_path/'queue.db')))
    unsupported=manager.create('Not for this worker',{'tool':'process.run@1.0.0',
        'execution_target':'remote','assigned_knight':'worker','capability':'compute'})
    supported=manager.create('Source',{'tool':'code.python.analyze@1.0.0',
        'execution_target':'remote','assigned_knight':'worker','capability':'compute'})
    monkeypatch.setattr(api.engine,'tasks',manager)
    monkeypatch.setattr(api.engine.execution_policy,'get',lambda:{'level':5})
    monkeypatch.setattr(api.capability_authorizer,'is_capability_granted',lambda *a:True)
    claimed=[]
    def dispatch(ident,*args):
        claimed.append(ident)
        return manager.transition_task(ident,'leased',{'lease_id':'exact-lease','fencing_token':1})
    monkeypatch.setattr(api.engine,'dispatch_remote_task',dispatch)
    monkeypatch.setattr(api.RPCSecureTransport,'verify_and_unwrap_message',lambda *a,**kw:{
        'valid':True,'sender_id':'worker','msg_type':'task_poll','payload':{
            'supported_tools':['text.analyze@1.0.0','code.python.analyze@1.0.0']}})
    result=api.handle_cluster_rpc(SimpleNamespace(model_dump=lambda:{}))
    assert claimed==[supported['id']]
    assert result['tasks'][0]['id']==supported['id']
    untouched=manager.get(unsupported['id'])
    assert untouched['status']=='queued' and not untouched.get('lease_id')


@pytest.mark.parametrize('transport',['worker','inventory'])
def test_ssh_python_input_is_explicit_utf8(monkeypatch,transport):
    from types import SimpleNamespace
    seen=[]
    def run(argv,**kwargs):
        assert kwargs['encoding']=='utf-8'
        source=kwargs['input']
        # Exercise the exact bytes sent to Python on non-UTF8 Windows locales.
        raw=source.encode(kwargs['encoding'])
        assert raw.decode('utf-8')==source
        compile(raw,'remote-stdin','exec')
        assert 'café' in source
        seen.append(raw)
        return SimpleNamespace(returncode=0,stdout='{}')
    monkeypatch.setattr(relay.subprocess,'run',run)
    host={'ssh':['ssh','pinned-host'],'python':'python3','cwd':'/tmp/café',
          'source_root':'/tmp/source','port':8012,'token_file':'data/owner-token'}
    if transport=='worker':
        relay.remote_worker(host,{'operation':'poll','worker_id':'worker','controller_id':'controller'})
    else:
        relay.inventory_api()(host,'/nodes/identity')
    assert len(seen)==1
