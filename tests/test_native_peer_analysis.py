from copy import deepcopy
from types import SimpleNamespace
import pytest
from backend.cluster.peer_analysis import PeerAnalysis,validate
from backend.cluster.identity import KingdomIdentity
from backend.cluster.node_registry import NodeInfo
from backend.storage.db import Database


def task():
    return {'id':'job','status':'leased','lease_id':'exact','fencing_token':3,'assigned_knight':'worker',
            'prompt':'syntax check','metadata':{'execution_target':'remote','capability':'compute',
            'tool':'code.python.analyze@1.0.0','tool_parameters':{'text':'def square(x): return x*x'}}}


def setup(tmp_path,monkeypatch,permitted=lambda:True):
    monkeypatch.setattr('backend.cluster.local_load.local_load_metrics',lambda:{'cpu_percent':10,'memory_percent':20,'power':{'status':'no_battery','plugged':None,'battery_percent':None}})
    node=NodeInfo('controller',fingerprint='pinned',public_identity={'node_id':'controller'},granted_capabilities=['compute'])
    calls=[];events=[]
    async def exchange(peer,message):
        calls.append(message)
        assert message['sender_id']=='worker' and message['target_id']=='controller' and message['signature']
        if message['msg_type']=='task_poll':
            assert message['payload']['require_running'] is True
            assert message['payload']['supported_tools']==['code.python.analyze@1.0.0','text.analyze@1.0.0']
            return {'status':'ok','tasks':[task()]}
        from backend.runtime.execution import verify_request_result
        payload=message['payload']
        checked=verify_request_result(task(),payload['output'],allow_local_model=False)
        assert checked['state']=='VERIFIED'
        return {'completed':{'id':'job','status':'completed','result':{'verification':checked,'executed_by':'worker'}}}
    worker=PeerAnalysis(Database(tmp_path/'worker.db'),SimpleNamespace(get_node=lambda _:node),
                        KingdomIdentity('worker'),permitted,exchange,lambda *a:events.append(a))
    return worker,node,calls,events


@pytest.mark.asyncio
async def test_real_native_execution_and_independent_controller_recomputation(tmp_path,monkeypatch):
    worker,node,calls,events=setup(tmp_path,monkeypatch)
    result=await worker.tick('controller')
    assert result=={'status':'verified','task_id':'job'}
    assert len(calls)==2 and calls[1]['payload']['lease_id']=='exact'
    assert events[-1][0]=='cluster.native_analysis_verified'
    with worker.db.get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM peer_analysis_receipts').fetchone()[0]==1
    # Re-delivered exact lease uses the durable result instead of executing again.
    monkeypatch.setattr('backend.runtime.execution.execute_request',lambda *a:pytest.fail('duplicate execution'))
    assert (await worker.tick('controller'))['status']=='verified'


@pytest.mark.asyncio
async def test_revocation_local_policy_and_low_battery_prevent_poll(tmp_path,monkeypatch):
    allowed=[False]
    worker,node,calls,_=setup(tmp_path,monkeypatch,lambda:allowed[0])
    assert (await worker.tick('controller'))['status']=='held' and not calls
    allowed[0]=True;node.granted_capabilities=[]
    assert (await worker.tick('controller'))['status']=='held' and not calls
    node.granted_capabilities=['compute'];node.connection_metadata={'membership_expires_at':1}
    assert (await worker.tick('controller'))['status']=='held' and not calls
    node.connection_metadata={}
    monkeypatch.setattr('backend.cluster.local_load.local_load_metrics',lambda:{'cpu_percent':10,'memory_percent':20,'power':{'status':'battery','plugged':False,'battery_percent':10}})
    assert (await worker.tick('controller'))['status']=='capacity_held' and not calls


@pytest.mark.parametrize('patch',[{'lease_id':''},{'fencing_token':True},{'assigned_knight':'other'},
                                {'metadata':{'tool':'process.run@1.0.0'}},{'status':'completed'}])
def test_invalid_leases_or_tools_never_execute(patch):
    value=deepcopy(task());value.update(patch)
    with pytest.raises(ValueError):validate(value,'worker')
