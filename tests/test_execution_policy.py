import asyncio
import pytest
from backend.runtime.engine import RuntimeEngine
from backend.runtime.policy import ExecutionPolicy
from backend.runtime.tasks import TaskManager
from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.security.approval_engine import ApprovalEngine
from backend.main import app
from backend.api import engine as api_engine
from tests.auth_support import owner_client
from fastapi.testclient import TestClient

@pytest.fixture
def engine(tmp_path):
 database = Database(tmp_path / 'policy.db')
 runtime = RuntimeEngine()
 runtime.tasks = TaskManager(TaskRepository(database))
 runtime.execution_policy = ExecutionPolicy(database)
 runtime.security.approvals = ApprovalEngine(database=database)
 return runtime

def test_policy_persists_and_observer_does_not_claim_queued_work(engine):
 engine.set_autonomy(0)
 task = engine.submit_task('synthetic text', {'actor':'owner','tool':'text.analyze@1.0.0'})
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(task['id'])['status'] == 'queued'
 assert ExecutionPolicy(engine.execution_policy.db).get()['level'] == 0
 engine.set_autonomy(1)
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(task['id'])['status'] == 'completed'
 assert any(e['event_type']=='runtime.autonomy_changed' for e in engine.events.history(50))

def test_approve_every_task_consumes_exact_human_approval(engine):
 engine.set_autonomy(2)
 task = engine.submit_task('synthetic analysis task', {'actor':'owner','tool':'text.analyze@1.0.0'})
 asyncio.run(engine._process_next_task())
 waiting = engine.tasks.get(task['id'])
 assert waiting['status']=='WAITING_APPROVAL'
 approval = waiting['metadata']['approval_id']
 assert engine.security.approvals.get_request(approval)['status']=='pending'
 engine.security.approvals.approve(approval,approver='owner')
 engine.tasks.transition_task(task['id'],'queued')
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(task['id'])['status']=='completed'
 assert engine.security.approvals.get_request(approval)['status']=='consumed'
 another = engine.submit_task('different task', {'actor':'owner','tool':'text.analyze@1.0.0','approval_id':approval})
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(another['id'])['status']=='WAITING_APPROVAL'

def test_safe_analysis_requires_approval_for_models_and_never_grants_capabilities(engine):
 engine.set_autonomy(1)
 task = engine.submit_task('synthetic model prompt', {'actor':'owner'})
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(task['id'])['status']=='WAITING_APPROVAL'
 engine.set_autonomy(3)
 denied = engine.submit_task('read synthetic text', {'actor':'unregistered-test-actor','tool':'text.analyze@1.0.0'})
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(denied['id'])['status']=='failed'

def test_policy_api_owner_only_and_rejects_unsupported_levels(monkeypatch,tmp_path):
 monkeypatch.setattr(api_engine,'execution_policy',ExecutionPolicy(Database(tmp_path/'api-policy.db')))
 assert TestClient(app).get('/runtime/policy').status_code==401
 assert TestClient(app).put('/runtime/policy',json={'level':0}).status_code in {401,403}
 client=owner_client(app)
 assert client.put('/runtime/policy',json={'level':2}).json()['level']==2
 for level in [-1,4,5,True,'3']:
  assert client.put('/runtime/policy',json={'level':level}).status_code==422
 assert client.get('/runtime/policy').json()['level']==2


def test_remote_dispatch_obeys_observer_and_exact_approval_boundary(engine):
 from backend.cluster.task_leasing import TaskLeaseManager
 leases=TaskLeaseManager(database=engine.execution_policy.db)
 task=engine.submit_task('remote synthetic analysis',{'actor':'owner','tool':'text.analyze@1.0.0','capability':'compute','execution_target':'remote'})
 engine.set_autonomy(0)
 assert engine.dispatch_remote_task(task['id'],'test-remote-node','compute',leases) is None
 assert engine.tasks.get(task['id'])['status']=='queued'
 engine.set_autonomy(2)
 assert engine.dispatch_remote_task(task['id'],'test-remote-node','compute',leases) is None
 waiting=engine.tasks.get(task['id'])
 assert waiting['status']=='WAITING_APPROVAL'
 approval=waiting['metadata']['approval_id']
 engine.security.approvals.approve(approval,approver='owner')
 engine.tasks.transition_task(task['id'],'queued')
 claimed=engine.dispatch_remote_task(task['id'],'test-remote-node','compute',leases)
 assert claimed['status'].lower()=='leased'
 assert engine.security.approvals.get_request(approval)['status']=='consumed'
 assert engine.dispatch_remote_task(task['id'],'other-node','compute',leases) is None

def test_cancel_waiting_task_also_cancels_its_pending_approval(engine):
 engine.set_autonomy(2)
 task=engine.submit_task('synthetic pending task',{'actor':'owner','tool':'text.analyze@1.0.0'})
 asyncio.run(engine._process_next_task())
 waiting=engine.tasks.get(task['id'])
 approval=waiting['metadata']['approval_id']
 assert engine.cancel_task(task['id'])['status']=='cancelled'
 assert engine.security.approvals.get_request(approval)['status']=='cancelled'
 asyncio.run(engine._process_next_task())
 assert engine.tasks.get(task['id'])['status']=='cancelled'

def test_runtime_modes_change_real_queue_polling_cadence(engine):
 from backend.state import STATE
 previous=STATE['mode']
 try:
  engine.set_autonomy(0)
  engine.set_mode('burst');asyncio.run(engine._process_next_task());assert engine.scheduler._interval_seconds==0.02
  engine.set_mode('persistent');asyncio.run(engine._process_next_task());assert engine.scheduler._interval_seconds==0.1
  engine.set_mode('adaptive');asyncio.run(engine._process_next_task());assert engine.scheduler._interval_seconds==0.5
 finally: STATE['mode']=previous
