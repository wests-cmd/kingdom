"""Real MissionService, process executions and durable receipts; no model or network."""
import sys
from types import SimpleNamespace

import pytest

from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.runtime.tasks import TaskManager
from backend.runtime.missions import MissionService, MissionPlan, validate_plan
from backend.runtime.work_backlog import WorkBacklog
from backend.runtime.mission_acceptance import validated_acceptance


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'data').mkdir()
    Database(tmp_path / 'data/kingdom.db')
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(workspace))
    # A separate, fixed test file, rather than an injected passing summary.
    (workspace / 'test_section.py').write_text(
        'import unittest\nclass Section(unittest.TestCase):\n'
        '    def test_sum(self): self.assertEqual(sum([2,3]),5)\n', encoding='utf-8')
    database = Database(tmp_path / 'state.db')
    tasks = TaskManager(TaskRepository(database))
    policy = {'level': 5, 'mission_budget': {'max_steps': 10, 'max_parallel': 1, 'max_retries': 3, 'auto_advance': True}}
    engine = SimpleNamespace(tasks=tasks, submit_task=tasks.create,
        execution_policy=SimpleNamespace(get=lambda: policy), status=lambda: {'running': True},
        events=SimpleNamespace(publish=lambda *args: None))
    engine.missions = MissionService(engine, database)
    return engine, WorkBacklog(database, engine), workspace


def plan(argv=None, **changes):
    step = dict(id='suite', title='Run reviewed section suite', kind='project_test',
        argv=[sys.executable, '-m', 'unittest', 'test_section'] if argv is None else argv,
        project_test={'project': 'kingdom', 'source_revision': 'a'*40, 'runner': 'unittest', 'minimum_tests': 1},
        acceptance='Approved nonempty test summary only')
    step.update(changes)
    return MissionPlan(title='Section', objective='Run reviewed suite', deliverables=['Test report'], steps=[step])


def execute(engine):
    from backend.runtime.execution import execute_request, verify_request_result
    from backend.swarm.manager import execution_request
    task = engine.tasks.claim_next()
    child = execution_request(task, task['prompt'])
    outcome = execute_request(child, ['process.execute'])
    verification = verify_request_result(child, outcome)
    result = {'plan': {'task_id': task['id'], 'subtasks': [{'prompt': task['prompt'], 'knight': 'coder'}]},
              'results': [{'knight': 'coder', 'status': 'completed', 'verification': verification, 'outcome': outcome}]}
    engine.tasks.transition_task(task['id'], 'completed', {'result': result})
    return engine.tasks.get(task['id'])


def start(engine, queue, test_plan):
    mission = engine.missions.create(test_plan)
    mission = engine.missions.approve(mission['id'], 1)
    item = queue.register('kingdom', mission['id'], mission_id=mission['id'], mission_version=1,
                          acceptance_step='suite', enabled=True)
    queue.settings(True, queue.snapshot()['revision'])
    queue.tick()
    return mission, item


def test_real_project_suite_completes_backlog_with_declared_source_scope(runtime):
    engine, queue, _ = runtime
    mission, item = start(engine, queue, plan())
    task = execute(engine)
    assert task['metadata']['max_attempts'] == 1  # policy allows 3 retries; this tool never does
    assert task['metadata']['capability'] == 'process.execute'
    queue.tick()
    accepted = queue.get('kingdom', item['id'])
    assert accepted['status'] == 'completed'
    assert accepted['evidence']['tests_run'] == 1
    assert 'owner supplied' in accepted['evidence']['scope']
    assert accepted['evidence']['mission_id'] == mission['id']
    queue.tick()
    assert len(engine.tasks.list()) == 1


@pytest.mark.parametrize('command', [
    [sys.executable, '-c', 'print("no tests")'],
    [sys.executable, '-m', 'unittest', 'missing_suite'],
    [sys.executable, '-c', 'print("x"*70000); print("Ran 1 test in 0.1s\\n\\nOK")'],
])
def test_empty_failed_and_truncated_real_commands_do_not_complete(runtime, command):
    engine, queue, _ = runtime
    _, item = start(engine, queue, plan(argv=command))
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', item['id'])['status'] == 'review_required'


@pytest.mark.parametrize('change', ['argv', 'descriptor', 'version', 'receipt', 'task_binding', 'task_key'])
def test_current_review_and_receipt_drift_rejects_prior_success(runtime, change):
    engine, queue, _ = runtime
    mission, item = start(engine, queue, plan())
    task = execute(engine)
    queue.tick()
    assert queue.get('kingdom', item['id'])['status'] == 'completed'
    current = engine.missions.get(mission['id'])
    if change == 'argv': current['plan']['steps'][0]['argv'].append('changed')
    elif change == 'descriptor': current['plan']['steps'][0]['project_test']['source_revision'] = 'b'*40
    elif change == 'version': current['version'] += 1
    elif change == 'receipt':
        from pathlib import Path
        Path(task['result']['results'][0]['outcome']['artifact']).unlink()
    else:
        metadata = dict(task['metadata'], **({'step_id': 'different'} if change == 'task_binding'
                                           else {'_mission_step_key': 'different'}))
        engine.tasks.transition_task(task['id'], 'completed', {'metadata': metadata})
    engine.missions.save(current)
    with pytest.raises(ValueError): validated_acceptance(engine, mission['id'], 1, 'suite')
    queue.review()
    assert queue.get('kingdom', item['id'])['status'] == 'review_required'


@pytest.mark.parametrize('changes', [{'argv': []}, {'project_test': None}, {'input_from': 'generated'},
                                     {'argv': ['bad\x00command']}, {'repair_source': 'write'}])
def test_invalid_project_test_plan_rejected_before_dispatch(changes):
    with pytest.raises(ValueError): validate_plan(plan(**changes))


def test_process_capability_remains_required(runtime):
    engine, queue, _ = runtime
    start(engine, queue, plan())
    from backend.runtime.execution import execute_request
    task = engine.tasks.claim_next()
    with pytest.raises(PermissionError): execute_request(task, ['compute'])
