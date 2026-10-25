import time
from types import SimpleNamespace
from backend.cluster.hierarchy import offload_candidate
from backend.cluster.node_registry import NodeInfo

def nodes():
    return [NodeInfo(name, public_identity={'node_id':name}, fingerprint=name, granted_capabilities=['compute'],
                     connection_metadata={'load_metrics':{'cpu_percent':cpu,'memory_percent':20}})
            for name,cpu in [('fast',10),('steady',20)]]

def outcome(node,status='failed',tool='text.analyze@1.0.0',verified=False):
    return {'assigned_knight':node,'status':status,'metadata':{'execution_target':'remote','tool':tool},
            'result':{'executed_by':node,'verification':{'state':'VERIFIED'} if verified else {}}}

def test_repeated_failures_adapt_actual_load_selection():
    registry=SimpleNamespace(list_nodes=nodes)
    assert offload_candidate(registry,'compute')=='fast'
    assert offload_candidate(registry,'compute',outcomes=[outcome('fast')]*4,tool='text.analyze@1.0.0')=='steady'
    assert offload_candidate(registry,'compute',busy_nodes={'fast'})=='steady'
    assert offload_candidate(registry,'compute',busy_nodes={'fast','steady'}) is None

def test_other_tools_and_unverified_successes_cannot_improve_ranking():
    registry=SimpleNamespace(list_nodes=nodes)
    failures=[outcome('fast')]*4
    claims=[outcome('fast','completed',verified=False)]*90
    assert offload_candidate(registry,'compute',outcomes=failures+claims,tool='text.analyze@1.0.0')=='steady'
    assert offload_candidate(registry,'compute',outcomes=[outcome('fast',tool='other')]*4,tool='text.analyze@1.0.0')=='fast'

def test_verified_success_can_restore_preference_without_overriding_grants():
    items=nodes();registry=SimpleNamespace(list_nodes=lambda:items)
    history=[outcome('fast')]*2+[outcome('fast','completed',verified=True)]*30
    assert offload_candidate(registry,'compute',outcomes=history)=='fast'
    items[0].granted_capabilities=[]
    assert offload_candidate(registry,'compute',outcomes=history)=='steady'
    items[1].last_heartbeat=time.time()-60
    assert offload_candidate(registry,'compute',outcomes=history) is None


def test_shadow_selector_only_sees_current_eligible_workers():
    items=nodes();registry=SimpleNamespace(list_nodes=lambda:items)
    report={}
    items[0].granted_capabilities=[]
    assert offload_candidate(registry,'compute',decision_report=report)=='steady'
    assert report['knights']==['steady'] and report['affects_execution'] is False
    items[1].last_heartbeat=time.time()-60
    report={}
    assert offload_candidate(registry,'compute',decision_report=report) is None
    assert report['knights']==[] and report['count']==0
