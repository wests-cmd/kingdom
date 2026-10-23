"""The ordinary runtime must not select paused/dependency-blocked backlog work."""
import asyncio
from types import SimpleNamespace

import pytest

from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.runtime.tasks import TaskManager
from backend.runtime.missions import MissionService, MissionPlan
from backend.runtime.work_backlog import WorkBacklog


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'data').mkdir()
    Database(tmp_path / 'data/kingdom.db')
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    database = Database(tmp_path / 'runtime.db')
    tasks = TaskManager(TaskRepository(database))
    policy = {'level': 4, 'mission_budget': {'max_steps': 10, 'max_parallel': 1, 'max_retries': 0, 'auto_advance': True}}
    engine = SimpleNamespace(tasks=tasks, submit_task=tasks.create,
        execution_policy=SimpleNamespace(get=lambda: policy), status=lambda: {'running': True},
        events=SimpleNamespace(publish=lambda *args: None), scheduler=SimpleNamespace(),
        recover_remote_tasks=lambda: None, memory=SimpleNamespace(record_task=lambda *args: None))
    engine.missions = MissionService(engine, database)
    queue = WorkBacklog(database, engine)
    executed = []
    async def execute(task):
        from backend.runtime.execution import execute_request, verify_request_result
        from backend.swarm.manager import execution_request
        child = execution_request(task, task['prompt'])
        outcome = execute_request(child, {'compute', 'filesystem.read', 'filesystem.write'})
        verification = verify_request_result(child, outcome)
        executed.append(task['id'])
        return {'plan': {'task_id': task['id'], 'subtasks': [{'prompt': task['prompt'], 'knight': 'coder'}]},
                'results': [{'knight': 'coder', 'verification': verification, 'outcome': outcome}]}
    engine.swarm = SimpleNamespace(execute=execute)
    # This fixture grants only the explicit native operations above. The test
    # concerns selection; production authorization is independently unchanged.
    engine.authorize_task = lambda task: {'authorized': True}
    def poll():
        from backend.runtime.engine import RuntimeEngine
        asyncio.run(RuntimeEngine._process_next_task(engine))
    return engine, queue, poll, executed


def reviewed(engine):
    plan = MissionPlan(title='Reviewed function', objective='Bounded source and cases', deliverables=['solution.py'], steps=[
        {'id': 'write', 'title': 'Write source', 'kind': 'write_file', 'path': 'solution.py',
         'instructions': 'def bounded_batch_size(requested,pending,hard_limit):\n    return max(0,min(requested,pending,hard_limit))\n', 'acceptance': 'Retained source write'},
        {'id': 'read', 'title': 'Read source', 'kind': 'read_file', 'path': 'solution.py', 'depends_on': ['write'], 'acceptance': 'Retained read'},
        {'id': 'check', 'title': 'Check fixed cases', 'kind': 'function_check', 'depends_on': ['write', 'read'],
         'input_from': 'read', 'repair_source': 'write', 'case_profile': 'bounded_batch_size.v1', 'acceptance': 'Fixed cases only'}])
    mission = engine.missions.create(plan)
    return engine.missions.approve(mission['id'], 1)


def register(queue, mission, **changes):
    return queue.register('kingdom', mission['id'], mission_id=mission['id'], mission_version=1,
                          acceptance_step='check', **changes)


@pytest.mark.parametrize('pause', ['global', 'item'])
def test_actual_runtime_poll_cannot_advance_paused_tracked_mission(runtime, pause):
    engine, queue, poll, executed = runtime
    mission = reviewed(engine)
    register(queue, mission, enabled=pause == 'global')
    if pause == 'item':
        queue.settings(True, queue.snapshot()['revision'])
    assert queue.tick()['status'] in {'stopped', 'idle'}
    poll()
    assert not engine.tasks.list() and not executed
    assert engine.missions.get(mission['id'])['status'] == 'approved'
    with pytest.raises(ValueError, match='backlog selection'):
        engine.missions.advance(mission['id'])


def test_dependencies_cannot_be_bypassed_by_regular_runtime_or_direct_advance(runtime):
    engine, queue, poll, executed = runtime
    dependency = queue.register('kingdom', 'unfinished', title='Not yet reviewed')
    mission = reviewed(engine)
    register(queue, mission, enabled=True, depends_on=[dependency['id']])
    queue.settings(True, queue.snapshot()['revision'])
    assert queue.tick()['status'] == 'idle'
    poll()
    with pytest.raises(ValueError):
        engine.missions.advance(mission['id'], backlog_lease='unselected')
    assert not engine.tasks.list() and not executed


def test_selected_backlog_mission_advances_once_and_pause_does_not_replay_committed_tasks(runtime):
    engine, queue, poll, executed = runtime
    mission = reviewed(engine)
    item = register(queue, mission, enabled=True)
    queue.settings(True, queue.snapshot()['revision'])
    selected = queue.tick()
    assert selected['status'] == 'running'
    original, = engine.tasks.list()
    queue.configure('kingdom', item['id'], False, selected['revision'])
    # Selection pause does not cancel an already queued owner-reviewed operation.
    poll()
    assert executed == [original['id']]
    assert engine.tasks.get(original['id'])['status'] == 'completed'
    poll()
    assert len(engine.tasks.list()) == 1 and executed == [original['id']]
    with pytest.raises(ValueError):
        engine.missions.advance(mission['id'], backlog_lease='stale')
    resumed = queue.configure('kingdom', item['id'], True, queue.get('kingdom', item['id'])['revision'])
    queue.tick()
    assert len(engine.tasks.list()) == 2
    assert engine.missions.get(mission['id'])['steps']['write']['task_id'] == original['id']


def test_untracked_missions_preserve_ordinary_runtime_selection(runtime):
    engine, queue, poll, executed = runtime
    mission = reviewed(engine)
    assert queue.snapshot()['enabled'] is False
    poll()
    task, = engine.tasks.list()
    assert executed == [task['id']] and task['status'] == 'completed'
    assert engine.missions.get(mission['id'])['steps']['write']['task_id'] == task['id']
