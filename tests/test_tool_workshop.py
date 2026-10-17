import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.runtime.computer_tools import run_process, receipt, verify_receipt, workspace_path
from backend.runtime.harnesses import HarnessService
from backend.runtime.tool_workshop import ToolProposal, ToolWorkshop
from backend.storage.db import Database


class TaskEngine:
    """Test scheduler boundary; commands and independent receipts run for real."""
    def __init__(self):
        self.tasks = {}
        self.events = SimpleNamespace(publish=lambda *args: None)

    def submit_task(self, prompt, metadata):
        ident = uuid4().hex
        task = {'id': ident, 'status': 'WAITING_APPROVAL', 'metadata': metadata}
        self.tasks[ident] = task
        return task

    def get_task(self, ident):
        return self.tasks.get(ident)

    def cancel_task(self, ident):
        self.tasks[ident]['status'] = 'CANCELLED'

    def run_approved(self, ident):
        task = self.tasks[ident]
        output = run_process(task['metadata']['tool_parameters'])
        evidence = {**receipt(task, output), 'output': output}
        verified = verify_receipt(task, evidence)
        task.update(status='COMPLETED', result={'results': [{'verification': verified,
                    'outcome': {'tool': 'process.run@1.0.0', 'output': output}}]})


@pytest.fixture
def workshop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    return ToolWorkshop(TaskEngine(), Database(tmp_path / 'workshop.db'))


def proposal(**updates):
    data = dict(name='Echo helper', objective='Prepare a portable command helper', source='owner-authored',
        files={'helper.py': 'import sys\nprint(sys.argv[1])\n'},
        build={'argv': [sys.executable, '-c', 'from pathlib import Path;assert Path("helper.py").exists()']},
        test={'argv': [sys.executable, 'helper.py', 'verified']},
        connection={'name': 'Echo helper', 'argv': [sys.executable, '{staging}/helper.py', '{prompt}']})
    data.update(updates)
    return ToolProposal.model_validate(data)


def ready(workshop):
    state = workshop.propose(proposal())
    ident = state['id']
    assert workshop.advance(ident)['status'] == 'proposed'
    workshop.review(ident, state['checksum'])
    for stage in ('build', 'test'):
        state = workshop.advance(ident)
        assert state['status'] == 'waiting_' + stage
        assert workshop.advance(ident)['task_status'] == 'waiting_approval'
        workshop.engine.run_approved(state['task_id'])
        state = workshop.advance(ident)
    assert state['status'] == 'ready'
    return state


def test_real_build_test_evidence_then_explicit_registration(workshop):
    state = ready(workshop)
    assert len(state['evidence']) == 2
    assert 'verified' in state['evidence'][1]['output']['output']
    assert HarnessService(workshop.engine, workshop.db).list() == []
    saved = workshop.register(state['id'], state['checksum'], 'echo-helper')
    assert saved['status'] == 'registered'
    profile = HarnessService(workshop.engine, workshop.db).get('echo-helper')
    assert profile['argv'][1] == str(workspace_path(state['cwd'] + '/helper.py'))
    assert workshop.discover('echo')['connections'][0]['id'] == 'echo-helper'


def test_unverified_or_nonzero_output_never_ready(workshop):
    state = workshop.propose(proposal(build={'argv': [sys.executable, '-c', 'raise SystemExit(7)']}))
    workshop.review(state['id'], state['checksum'])
    waiting = workshop.advance(state['id'])
    workshop.engine.run_approved(waiting['task_id'])
    assert workshop.advance(state['id'])['status'] == 'failed'
    with pytest.raises(ValueError):
        workshop.register(state['id'], state['checksum'], 'failed')


def test_source_and_artifacts_cannot_change_after_review(workshop):
    state = ready(workshop)
    workspace_path(state['cwd'] + '/extra.py').write_text('changed')
    with pytest.raises(ValueError, match='artifacts changed'):
        workshop.register(state['id'], state['checksum'], 'changed')
    workspace_path(state['cwd'] + '/helper.py').write_text('changed')
    with pytest.raises(ValueError, match='source changed'):
        workshop.register(state['id'], state['checksum'], 'changed')


def test_review_checksum_disable_and_no_automatic_dispatch(workshop):
    state = workshop.propose(proposal())
    assert not workshop.engine.tasks
    with pytest.raises(ValueError):
        workshop.review(state['id'], '0' * 64)
    workshop.review(state['id'], state['checksum'])
    waiting = workshop.advance(state['id'])
    assert workshop.disable(state['id'])['status'] == 'disabled'
    assert workshop.engine.get_task(waiting['task_id'])['status'] == 'CANCELLED'
    assert workshop.advance(state['id'])['status'] == 'disabled'


@pytest.mark.parametrize('files', [{'../escape.py': 'x'}, {'C:/escape.py': 'x'}, {'large.py': 'x' * 524289}])
def test_unsafe_staging_rejected(files):
    with pytest.raises(ValueError):
        proposal(files=files)


def test_missing_and_unverified_task_fail_closed(workshop):
    state = workshop.propose(proposal())
    workshop.review(state['id'], state['checksum'])
    waiting = workshop.advance(state['id'])
    task = workshop.engine.get_task(waiting['task_id'])
    task.update(status='COMPLETED', result={'results': []})
    assert workshop.advance(state['id'])['status'] == 'failed'


def test_dependency_ranges_are_not_pins():
    with pytest.raises(ValueError):
        proposal(dependencies=[{'name': 'example', 'version': '>=1', 'source': 'registry', 'sha256': '0' * 64}])


def test_owner_auth_required_before_workshop_access(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.runtime.tool_workshop_api import router
    monkeypatch.setenv('KINGDOM_OWNER_TOKEN', 'workshop-owner-test')
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get('/tool-workshop').status_code in {401, 403}
