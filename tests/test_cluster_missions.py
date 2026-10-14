from types import SimpleNamespace
import time
from uuid import NAMESPACE_URL, uuid5

import pytest

from backend.runtime.missions import MissionPlan, MissionService, validate_plan
from backend.storage.db import Database


@pytest.fixture
def harness(tmp_path):
    tasks, submitted = {}, []
    policy = {'level': 5, 'mission_budget': {'max_steps': 50, 'max_parallel': 2,
              'max_retries': 1, 'auto_advance': True}}
    def submit(prompt, metadata):
        ident = str(uuid5(NAMESPACE_URL, 'kingdom-mission:' + metadata['_mission_step_key']))
        tasks[ident] = {'id': ident, 'status': 'queued', 'metadata': metadata}
        submitted.append((prompt, metadata))
    engine = SimpleNamespace(execution_policy=SimpleNamespace(get=lambda: policy),
        events=SimpleNamespace(publish=lambda *args: None),
        tasks=SimpleNamespace(get=tasks.get), submit_task=submit)
    return MissionService(engine, Database(tmp_path/'test.db')), tasks, submitted, policy


def plan(**kwargs):
    return MissionPlan(title='Cluster', objective='Verified dependency', deliverables=['analysis'],
        steps=[{'id': 'first', 'title': 'First', 'kind': 'text_check', 'instructions': 'source',
                'acceptance': 'Measured source', **kwargs},
               {'id': 'second', 'title': 'Second', 'kind': 'text_check', 'depends_on': ['first'],
                'input_from': 'first', 'acceptance': 'Consumes verified result'}])


def start(service, candidate):
    state = service.create(candidate)
    service.approve(state['id'], 1)
    return service.advance(state['id'])


def receipt(output, **kwargs):
    return {'output': output, 'executed_by': 'worker-a',
            'verification': {'state': 'VERIFIED'}, **kwargs}


def test_verified_remote_output_unblocks_bound_dependency(harness):
    service, tasks, submitted, _ = harness
    state = start(service, plan())
    first = tasks[state['steps']['first']['task_id']]
    assert len(submitted) == 1
    first.update(status='completed', assigned_knight='worker-a', result=receipt({'text': 'verified source'}))
    state = service.advance(state['id'])
    assert state['steps']['first']['status'] == 'verified'
    assert submitted[1][0] == 'verified source'
    second = tasks[state['steps']['second']['task_id']]
    second.update(status='completed', result=receipt({'text': 'done'}))
    assert service.advance(state['id'])['status'] == 'completed'


def test_rpc_native_envelope_binds_serializable_payload_to_next_task(harness):
    service, tasks, submitted, _ = harness
    state = start(service, plan())
    payload = {'words': 3, 'characters': 12}
    tasks[state['steps']['first']['task_id']].update(status='completed', assigned_knight='worker-a',
        result=receipt({'kind': 'native_tool', 'tool': 'text.analyze@1.0.0', 'output': payload}))
    service.advance(state['id'])
    import json
    assert isinstance(submitted[1][0], str)
    assert json.loads(submitted[1][0]) == payload


@pytest.mark.parametrize('value', [{'output': {'words': 3}}, {'text': ['one', 'two']}, ['a', 'b'], 42, None])
def test_bound_outputs_always_text(value):
    assert isinstance(MissionService.output({'result': receipt(value)}), str)


@pytest.mark.parametrize('result', [receipt('claim', verification={'state': 'UNVERIFIED'}),
    receipt('claim', executed_by='other-worker'), {'output': 'claim'},
    receipt({'exit_code': 2}), {'results': [], **receipt('ambiguous')}])
def test_remote_failure_never_releases_dependents(harness, result):
    service, tasks, submitted, _ = harness
    state = start(service, plan())
    tasks[state['steps']['first']['task_id']].update(status='completed', assigned_knight='worker-a', result=result)
    assert service.advance(state['id'])['status'] == 'needs_review'
    assert len(submitted) == 1


def test_explicit_worker_metadata_and_auto_offload_preserved(harness, monkeypatch):
    service, _, submitted, _ = harness
    import backend.cluster.hierarchy as hierarchy
    from backend.cluster.node_registry import node_registry
    monkeypatch.setattr(hierarchy, 'offload_candidate', lambda registry, capability, members: members[0])
    monkeypatch.setattr(node_registry, 'get_node', lambda ident: SimpleNamespace(fingerprint='paired'))
    start(service, plan(computer_id='worker-a'))
    metadata = submitted[0][1]
    assert metadata['assigned_knight'] == 'worker-a'
    assert metadata['execution_target'] == 'remote' and metadata['capability'] == 'compute'
    assert 'offload' not in metadata
    candidate = plan(); candidate.offload_analysis = True
    start(service, candidate)
    assert submitted[-1][1]['offload'] is True


@pytest.mark.parametrize('level,available,fingerprint', [(4,True,True), (5,False,True), (5,True,False)])
def test_unavailable_explicit_worker_never_silently_runs_locally(harness, monkeypatch, level, available, fingerprint):
    service, _, submitted, policy = harness
    import backend.cluster.hierarchy as hierarchy
    from backend.cluster.node_registry import node_registry
    policy['level'] = level
    monkeypatch.setattr(hierarchy, 'offload_candidate', lambda *args, **kwargs: 'worker-a' if available else None)
    monkeypatch.setattr(node_registry, 'get_node', lambda ident: SimpleNamespace(fingerprint='paired' if fingerprint else None))
    assert start(service, plan(computer_id='worker-a'))['status'] == 'needs_review'
    assert not submitted


def test_unsupported_remote_operation_rejected():
    candidate = plan(); candidate.steps[0].kind = 'command'; candidate.steps[0].argv = ['whoami']
    candidate.steps[0].computer_id = 'worker-a'
    with pytest.raises(ValueError, match='only independently verified'):
        validate_plan(candidate)


def test_explicit_worker_receipt_must_match_reviewed_plan_even_after_assignment_lost(harness, monkeypatch):
    service, tasks, submitted, _ = harness
    import backend.cluster.hierarchy as hierarchy
    from backend.cluster.node_registry import node_registry
    monkeypatch.setattr(hierarchy, 'offload_candidate', lambda *args, **kwargs: 'worker-a')
    monkeypatch.setattr(node_registry, 'get_node', lambda ident: SimpleNamespace(fingerprint='paired'))
    state = start(service, plan(computer_id='worker-a'))
    tasks[state['steps']['first']['task_id']].update(status='completed', assigned_knight=None,
        result=receipt('wrong computer', executed_by='worker-b'))
    assert service.advance(state['id'])['status'] == 'needs_review'
    assert len(submitted) == 1


@pytest.mark.parametrize('changes', [
    {'node_state': 'REVOKED'}, {'public_identity': None},
    {'last_heartbeat': 0}, {'health': 'degraded'}, {'current_task': 'busy'},
    {'granted_capabilities': []}, {'is_local': True},
    {'connection_metadata': {'load_metrics': {'cpu_percent': 99, 'memory_percent': 20}}},
])
def test_real_placement_eligibility_blocks_untrusted_or_unavailable_worker(harness, monkeypatch, changes):
    service, _, submitted, _ = harness
    from backend.cluster.node_registry import node_registry
    fields = dict(node_id='worker-a', node_state='CONNECTED', public_identity={'key': 'paired'},
        fingerprint='paired', last_heartbeat=time.time(), health='healthy', current_task=None,
        granted_capabilities=['compute'], is_local=False,
        connection_metadata={'load_metrics': {'cpu_percent': 20, 'memory_percent': 20}})
    fields.update(changes)
    node = SimpleNamespace(**fields)
    monkeypatch.setattr(node_registry, 'list_nodes', lambda: [node])
    monkeypatch.setattr(node_registry, 'get_node', lambda ident: node)
    assert start(service, plan(computer_id='worker-a'))['status'] == 'needs_review'
    assert not submitted
