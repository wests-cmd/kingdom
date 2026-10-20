import pytest
from backend.cluster.power_policy import power_budget,validate_power


def battery(percent,plugged=False):
    return {'status':'battery','battery_percent':percent,'plugged':plugged}


def test_long_work_requires_charging_or_no_battery():
    assert not power_budget(battery(90),180)['allowed']
    assert power_budget(battery(10,True),180)['allowed']
    assert power_budget({'status':'no_battery','battery_percent':None,'plugged':None},180)['allowed']


def test_on_battery_only_short_work_with_reserve():
    assert power_budget(battery(80),30)['allowed']
    assert not power_budget(battery(35),30)['allowed']
    assert power_budget(battery(35),10)['allowed']
    assert not power_budget(battery(15),1)['allowed']


def test_unknown_never_enables_long_jobs():
    assert not power_budget(None,180)['allowed']
    assert power_budget(None,10)['allowed']
    assert power_budget(None,10)['power_status']=='unknown'


@pytest.mark.parametrize('value',[battery(True),battery(101),battery(30,1),{'status':'unknown','battery_percent':80,'plugged':True}])
def test_invalid_power_report_rejected(value):
    with pytest.raises(ValueError):validate_power(value)


def test_offload_skips_low_battery_even_with_idle_cpu(monkeypatch):
    import time
    from types import SimpleNamespace
    from backend.cluster.hierarchy import offload_candidate
    node=SimpleNamespace(node_id='portable',is_local=False,public_identity={'node_type':'commander'},node_state='CONNECTED',
      last_heartbeat=time.time(),health='healthy',current_task=None,granted_capabilities=['compute'],
      connection_metadata={'load_metrics':{'cpu_percent':1,'memory_percent':1,'power':battery(5)}})
    assert offload_candidate(SimpleNamespace(list_nodes=lambda:[node]),'compute') is None
    node.connection_metadata['load_metrics']['power']=battery(50,True)
    assert offload_candidate(SimpleNamespace(list_nodes=lambda:[node]),'compute')=='portable'


def test_worker_rechecks_battery_before_executing_a_lease(monkeypatch):
    from backend.cluster.knight_daemon import KnightDaemon
    worker=KnightDaemon.__new__(KnightDaemon);worker.node_id='portable';worker.granted_capabilities=['compute']
    task={'id':'leased','lease_id':'lease','fencing_token':1,'metadata':{'tool':'text.analyze@1.0.0'}}
    submitted=[]
    def rpc(kind,payload):
        if kind=='task_poll':return {'tasks':[task]}
        submitted.append(payload);return {'status':'ok'}
    worker.send_rpc=rpc
    monkeypatch.setattr('backend.cluster.local_load.local_load_metrics',lambda:{'power':battery(5)})
    def forbidden(*args):raise AssertionError('Low-battery worker must not execute')
    monkeypatch.setattr('backend.runtime.execution.execute_request',forbidden)
    result=worker.poll_and_execute_task()
    assert result['status']=='failed' and 'Battery reserve' in result['error']
    assert submitted==[result]
