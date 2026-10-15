import base64
from copy import deepcopy
import hashlib
import os

import pytest

from backend.runtime.remote_build import TOOL, BuildSpec, build, source_digest, verify
from backend.runtime.execution import execute_request, verify_request_result


@pytest.fixture
def task():
    files = {'build.py': "from pathlib import Path\nPath('artifact.txt').write_bytes(b'BUILT\\n')\n"}
    return {'id': 'build-test', 'prompt': 'Build the reviewed source', 'lease_id': 'lease-test', 'fencing_token': 1,
            'metadata': {'tool': TOOL, 'tool_parameters': {'source_revision': 'a'*40,
                'source_sha256': source_digest(files), 'files': files, 'argv': ['@python', 'build.py'],
                'expected_artifacts': {'artifact.txt': hashlib.sha256(b'BUILT\n').hexdigest()}}}}


def outcome(task):
    spec = task['metadata']['tool_parameters']
    return {'task_id': task['id'], 'lease_id': task['lease_id'], 'fencing_token': task['fencing_token'],
            'source_revision': spec['source_revision'], 'source_sha256': spec['source_sha256'], 'argv': spec['argv'],
            'exit_code': 0, 'artifacts': {'artifact.txt': {'sha256': spec['expected_artifacts']['artifact.txt'],
                'base64': base64.b64encode(b'BUILT\n').decode()}}}


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/disk', 'dir\\escape', 'dir/../escape', 'a//b'])
def test_source_paths_cannot_escape_bundle(task, path):
    spec = task['metadata']['tool_parameters']; spec['files'] = {path: 'x'}
    spec['source_sha256'] = source_digest(spec['files'])
    with pytest.raises(ValueError): BuildSpec.model_validate(spec)


@pytest.mark.parametrize('field,value', [('task_id', 'other'), ('lease_id', 'old'), ('fencing_token', 2),
    ('source_revision', 'b'*40), ('source_sha256', '0'*64), ('argv', ['other']), ('exit_code', 1)])
def test_receipt_is_bound_to_exact_review_and_lease(task, field, value):
    output = outcome(task); output[field] = value
    with pytest.raises(ValueError): verify(task, output)


def test_controller_rehashes_actual_bytes_not_worker_claim(task):
    output = outcome(task)
    assert verify(task, output)['state'] == 'VERIFIED'
    output['artifacts']['artifact.txt']['base64'] = base64.b64encode(b'TAMPERED').decode()
    with pytest.raises(ValueError, match='Independent'): verify(task, output)


def test_budgets_digest_and_unknown_parameters_fail_closed(task):
    for change in ({'timeout_seconds': 100}, {'source_sha256': '0'*64}, {'environment': {'TOKEN': 'bad'}}):
        with pytest.raises(ValueError): BuildSpec.model_validate({**task['metadata']['tool_parameters'], **change})


def test_compute_grant_cannot_execute_build(task):
    with pytest.raises(Exception, match='capability'):
        execute_request(task, ['compute'])


def test_mission_build_needs_exact_computer_and_no_generated_bindings(task):
    from backend.runtime.missions import MissionPlan, validate_plan
    step={'id':'build','title':'Build package','kind':'build','computer_id':'linux-worker',
          'build':task['metadata']['tool_parameters'],'acceptance':'Artifact matches reviewed bytes'}
    candidate=MissionPlan(title='Build',objective='Build exact source',deliverables=['artifact'],steps=[step])
    assert validate_plan(candidate)
    candidate.steps[0].computer_id=None
    with pytest.raises(ValueError):validate_plan(candidate)
    candidate.steps[0].computer_id='linux-worker';candidate.steps[0].input_from='generated'
    with pytest.raises(ValueError):validate_plan(candidate)


def test_build_capability_cannot_be_downgraded_and_approval_is_required(task, tmp_path, monkeypatch):
    from types import SimpleNamespace
    import time
    from backend.runtime.engine import RuntimeEngine
    from backend.runtime.tasks import TaskManager
    from backend.runtime.policy import ExecutionPolicy
    from backend.storage.db import Database
    from backend.storage.repository import TaskRepository
    from backend.cluster.task_leasing import TaskLeaseManager
    from backend.security.approval_engine import ApprovalEngine
    database=Database(tmp_path/'approval.db')
    runtime=RuntimeEngine();runtime.tasks=TaskManager(TaskRepository(database))
    runtime.execution_policy=ExecutionPolicy(database)
    runtime.security.approvals=ApprovalEngine(database=database)
    metadata={**task['metadata'],'actor':'owner','execution_target':'remote','assigned_knight':'worker','capability':'compute'}
    submitted=runtime.submit_task(task['prompt'],metadata)
    assert submitted['metadata']['capability']=='process.execute'
    assert submitted['max_attempts']==1
    node=SimpleNamespace(node_id='worker',is_local=False,public_identity={'key':'paired'},node_state='CONNECTED',
        last_heartbeat=time.time(),health='healthy',current_task=None,granted_capabilities=['process.execute'],
        connection_metadata={'load_metrics':{'cpu_percent':1,'memory_percent':1}})
    monkeypatch.setattr('backend.cluster.node_registry.node_registry.list_nodes',lambda:[node])
    leases=TaskLeaseManager(database=database)
    assert runtime.dispatch_remote_task(submitted['id'],'worker','process.execute',leases) is None
    pending=runtime.tasks.get(submitted['id'])
    assert pending['status']=='WAITING_APPROVAL'
    approval=pending['metadata']['approval_id']
    runtime.security.approvals.approve(approval,approver='owner')
    runtime.tasks.transition_task(submitted['id'],'queued')
    assert runtime.dispatch_remote_task(submitted['id'],'worker','process.execute',leases)['status']=='leased'
    assert runtime.security.approvals.get_request(approval)['status']=='consumed'


@pytest.mark.skipif(os.name != 'posix', reason='Real process-group build execution requires a POSIX worker')
def test_real_command_builds_and_controller_checks_bytes(task):
    result = execute_request(task, ['process.execute'])
    assert base64.b64decode(result['output']['artifacts']['artifact.txt']['base64']) == b'BUILT\n'
    assert verify_request_result(task, result, allow_local_model=False)['state'] == 'VERIFIED'


@pytest.mark.skipif(os.name != 'posix', reason='Real process-group timeout requires a POSIX worker')
def test_real_timeout_stops_build(task):
    spec = task['metadata']['tool_parameters']
    spec['files']['build.py'] = 'import time\ntime.sleep(10)\n'
    spec['source_sha256'] = source_digest(spec['files']); spec['timeout_seconds'] = 1
    with pytest.raises(Exception, match='budget'): execute_request(task, ['process.execute'])


@pytest.mark.skipif(os.name != 'posix', reason='Real artifact checks require a POSIX worker')
@pytest.mark.parametrize('source', ["raise SystemExit(1)", "print('no artifact')",
    "from pathlib import Path\nPath('artifact.txt').symlink_to('/etc/passwd')"])
def test_failed_missing_and_symlinked_artifacts_never_pass(task, source):
    spec = task['metadata']['tool_parameters']; spec['files']['build.py'] = source
    spec['source_sha256'] = source_digest(spec['files'])
    with pytest.raises(Exception): execute_request(task, ['process.execute'])
