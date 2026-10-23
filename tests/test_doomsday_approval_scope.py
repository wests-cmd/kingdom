import pytest
from tests.test_execution_policy import engine


def test_DOOMSDAY_APPROVAL_SCOPE_ESCALATION_remote_node_substitution(engine):
    from backend.cluster.task_leasing import TaskLeaseManager
    engine.set_autonomy(2)
    leases = TaskLeaseManager(database=engine.execution_policy.db)
    task = engine.submit_task('maintain approved resource', {'actor': 'owner', 'tool': 'text.analyze@1.0.0', 'capability': 'compute', 'execution_target': 'remote'})
    assert engine.dispatch_remote_task(task['id'], 'approved-node', 'compute', leases) is None
    approval = engine.tasks.get(task['id'])['metadata']['approval_id']
    engine.security.approvals.approve(approval, approver='owner')
    engine.tasks.transition_task(task['id'], 'queued')
    assert engine.dispatch_remote_task(task['id'], 'substituted-node', 'compute', leases) is None
    assert engine.security.approvals.get_request(approval)['status'] == 'approved'

@pytest.mark.parametrize('change', ['task', 'prompt', 'argv', 'resource', 'actor', 'policy', 'dispatch_capability'])
def test_DOOMSDAY_APPROVAL_SCOPE_ESCALATION_context_changes(engine, change):
    from copy import deepcopy
    engine.set_autonomy(2)
    task = engine.submit_task('approved maintenance', {'actor': 'owner', 'tool': 'text.analyze@1.0.0', 'argv': ['check', '--safe'], 'resource': 'project-a'})
    first = engine.authorize_task(task, execution_node='node-a', execution_capability='compute')
    approval = first['approval_id']
    engine.security.approvals.approve(approval, approver='owner')
    altered = deepcopy(task)
    altered['metadata']['approval_id'] = approval
    dispatch_capability = 'compute'
    if change == 'task': altered['id'] = 'other-task'
    if change == 'prompt': altered['prompt'] = 'different maintenance'
    if change == 'argv': altered['metadata']['argv'] = ['check', '--unsafe']
    if change == 'resource': altered['metadata']['resource'] = 'project-b'
    if change == 'actor': altered['metadata']['actor'] = 'system'
    if change == 'policy': engine.execution_policy.set(2)
    if change == 'dispatch_capability': dispatch_capability = 'process.execute'
    result = engine.authorize_task(altered, execution_node='node-a', execution_capability=dispatch_capability)
    assert not result['authorized']
    assert engine.security.approvals.get_request(approval)['status'] == 'approved'
    if change != 'actor':
        assert any(row['decision'] == 'DENIED' and row['approval_id'] == approval for row in engine.security.audit.history(100))


def test_DOOMSDAY_APPROVAL_SCOPE_ESCALATION_restart_single_use_and_expiry(engine):
    from concurrent.futures import ThreadPoolExecutor
    from backend.security.approval_engine import ApprovalEngine
    request = engine.security.approvals.create_request(capability='process.execute', operation='specific command', requesting_actor='owner', parameters={'argv': ['check'], 'resource': 'a'})
    approval = request['id']
    engine.security.approvals.approve(approval, approver='owner')
    def spend(_):
        restarted = ApprovalEngine(database=engine.execution_policy.db)
        return restarted.consume(approval, actor_id='owner', capability='process.execute', operation='specific command', parameters={'argv': ['check'], 'resource': 'a'})
    with ThreadPoolExecutor(max_workers=4) as workers:
        assert list(workers.map(spend, range(4))).count(True) == 1
    expired = engine.security.approvals.create_request(capability='process.execute', operation='old', requesting_actor='owner', ttl_seconds=-1)
    assert not engine.security.approvals.consume(expired['id'], actor_id='owner', capability='process.execute', operation='old', parameters={})


def test_policy_revision_changes_even_when_clock_and_level_do_not(engine, monkeypatch):
    monkeypatch.setattr('backend.runtime.policy.time.time', lambda: 1000.0)
    first = engine.execution_policy.set(2)
    second = engine.execution_policy.set(2)
    assert first['revision'] != second['revision']


def test_local_approval_cannot_be_spent_on_remote_node_named_local(engine):
    engine.set_autonomy(2)
    task = engine.submit_task('scope placement', {'actor': 'owner', 'tool': 'text.analyze@1.0.0'})
    approval = engine.authorize_task(task)['approval_id']
    engine.security.approvals.approve(approval, approver='owner')
    task['metadata']['approval_id'] = approval
    assert not engine.authorize_task(task, execution_node='local')['authorized']
    assert engine.authorize_task(task)['authorized']
    assert not engine.authorize_task(task)['authorized']
