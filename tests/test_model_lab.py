import json
import sys
from types import SimpleNamespace
from uuid import uuid5, NAMESPACE_URL
import pytest
from backend.runtime.model_lab import ModelLabService, PreparationRequest
from backend.storage.db import Database


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    records = {}
    def submit(prompt, metadata):
        ident = str(uuid5(NAMESPACE_URL, 'kingdom-mission:' + metadata['_mission_step_key']))
        records[ident] = {'id': ident, 'metadata': metadata, 'status': 'WAITING_APPROVAL'}
        return records[ident]
    engine = SimpleNamespace(tasks=SimpleNamespace(get=records.get), submit_task=submit,
                             events=SimpleNamespace(publish=lambda *args: None))
    database = Database(tmp_path / 'lab.db')
    service = ModelLabService(engine, database)
    return service, records, tmp_path, monkeypatch


def request(**kwargs):
    return PreparationRequest(operation='custom', executable=sys.executable, base_model='local/base',
        output_path='models/candidate', argv=['trainer.py', '{base_model}', '{output}'], rollback_model_profile='stable',
        downloads_authorized=True, **kwargs)


def finished(record):
    record.update(status='completed', result={'results': [{'outcome': {'tool': 'harness.run@1.0.0', 'output': {'exit_code': 0}},
        'verification': {'state': 'VERIFIED'}}]})


def ready(lab):
    service, records, root, monkeypatch = lab
    monkeypatch.setattr('backend.runtime.model_lab.hardware_snapshot', lambda: {'ram_gb': 64, 'vram_gb': 24, 'disk_gb': 200})
    state = service.start(service.create(request())['id'])
    finished(records[state['preparation_task_id']])
    artifact = root / 'workspace/models/candidate'; artifact.mkdir(parents=True)
    (artifact / 'config.json').write_text('{}')
    (artifact / 'model.safetensors').write_bytes(b'synthetic model weights for test')
    return service.refresh(state['id'])


def test_hardware_blocks_without_dispatch(lab):
    service, records, _, monkeypatch = lab
    monkeypatch.setattr('backend.runtime.model_lab.hardware_snapshot', lambda: {'ram_gb': 4, 'vram_gb': 0, 'disk_gb': 10})
    state = service.start(service.create(request())['id'])
    assert state['status'] == 'hardware_blocked'
    assert 'vram_gb' in state['missing_hardware']
    assert not records


def test_successful_exit_is_not_model_completion(lab):
    service, records, _, monkeypatch = lab
    monkeypatch.setattr('backend.runtime.model_lab.hardware_snapshot', lambda: {'ram_gb': 64, 'vram_gb': 24, 'disk_gb': 200})
    state = service.start(service.create(request())['id'])
    assert records[state['preparation_task_id']]['status'] == 'WAITING_APPROVAL'
    assert service.refresh(state['id'])['status'] == 'preparing'
    finished(records[state['preparation_task_id']])
    with pytest.raises(ValueError, match='config.json'): service.refresh(state['id'])
    with pytest.raises(ValueError, match='passing'): service.promote(state['id'])


def test_passing_evaluation_and_artifact_binding_required_for_promotion(lab):
    state = ready(lab)
    service, records, root, _ = lab
    assert state['status'] == 'awaiting_evaluation'
    state = service.evaluate(state['id'], [sys.executable, 'evaluate.py'], 'evaluation.json')
    finished(records[state['evaluation_task_id']])
    report = root / 'workspace/evaluation.json'
    report.write_text(json.dumps({'passed': True, 'base_model': 'local/base', 'artifact_sha256': 'wrong', 'metrics': {'accuracy': 1}}))
    with pytest.raises(ValueError, match='bind'): service.refresh(state['id'])
    report.write_text(json.dumps({'passed': True, 'base_model': 'local/base', 'artifact_sha256': state['artifact']['sha256'], 'metrics': {'accuracy': 1}}))
    assert service.refresh(state['id'])['status'] == 'evaluated'
    assert service.promote(state['id'])['status'] == 'promoted'
    assert service.rollback(state['id'])['status'] == 'withdrawn'


def test_artifact_mutation_blocks_promotion(lab):
    state = ready(lab)
    service, _, root, _ = lab
    state['status'] = 'evaluated'; service._save(state)
    (root / 'workspace/models/candidate/model.safetensors').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'): service.promote(state['id'])


def test_heretic_uses_verified_noninteractive_recipe(lab):
    service, _, _, _ = lab
    data = request().model_dump(); data.update(operation='heretic', argv=[])
    state = service.create(PreparationRequest.model_validate(data))
    assert '--model-action' in state['argv'] and 'save' in state['argv']
    assert '--export-strategy' in state['argv'] and 'merge' in state['argv']
    assert state['status'] == 'draft'


def test_fine_tuning_requires_dataset_provenance(lab):
    service, _, _, _ = lab
    data = request().model_dump(); data.update(operation='fine_tune')
    with pytest.raises(ValueError, match='provenance'): service.create(PreparationRequest.model_validate(data))


def test_no_download_authorization_never_dispatches(lab):
    service, records, _, monkeypatch = lab
    monkeypatch.setattr('backend.runtime.model_lab.hardware_snapshot', lambda: {'ram_gb': 64, 'vram_gb': 24, 'disk_gb': 200})
    data = request().model_dump(); data.update(downloads_authorized=False)
    state = service.create(PreparationRequest.model_validate(data))
    with pytest.raises(ValueError, match='authorize'): service.start(state['id'])
    assert not records


@pytest.mark.asyncio
async def test_real_runtime_requires_exact_approval_before_preparation_process(tmp_path, monkeypatch):
    from backend.runtime.engine import RuntimeEngine
    from backend.runtime.tasks import TaskManager
    from backend.runtime.policy import ExecutionPolicy
    from backend.security.approval_engine import ApprovalEngine
    from backend.storage.repository import TaskRepository
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    monkeypatch.setattr('backend.runtime.model_lab.hardware_snapshot', lambda: {'ram_gb': 64, 'vram_gb': 24, 'disk_gb': 200})
    database = Database(tmp_path / 'real.db')
    Database(tmp_path / 'data/kingdom.db')
    engine = RuntimeEngine()
    engine.tasks = TaskManager(TaskRepository(database))
    engine.execution_policy = ExecutionPolicy(database)
    engine.security.approvals = ApprovalEngine(database=database)
    for role in engine.swarm.registry._knights:
        engine.grant_computer_tools(role, ['process.execute'], persist=False)
    service = ModelLabService(engine, database)
    script = ('import pathlib,sys; p=pathlib.Path(sys.argv[2]);p.mkdir(parents=True);'
              '(p/"config.json").write_text("{}");(p/"model.safetensors").write_bytes(b"test artifact")')
    data = request().model_dump(); data['argv'] = ['-c', script, '{base_model}', '{output}']
    state = service.start(service.create(PreparationRequest.model_validate(data))['id'])
    await engine._process_next_task()
    task = engine.tasks.get(state['preparation_task_id'])
    assert task['status'] == 'WAITING_APPROVAL'
    assert not (tmp_path / 'workspace/models/candidate').exists()
    approval = task['metadata']['approval_id']
    engine.security.approvals.approve(approval, approver='owner')
    engine.tasks.transition_task(task['id'], 'queued')
    await engine._process_next_task()
    task = engine.tasks.get(task['id'])
    assert task['status'] == 'completed'
    assert engine.security.approvals.get_request(approval)['status'] == 'consumed'
    assert service.refresh(state['id'])['status'] == 'awaiting_evaluation'


def test_model_lab_api_requires_owner():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.runtime.model_lab_api import router
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/model-lab').status_code in {401, 403, 503}
