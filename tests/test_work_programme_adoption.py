"""Existing owner notes become programme inputs, never implicit execution grants."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.runtime.work_programmes import WorkProgrammes
from test_project_test_missions import runtime, plan, execute


def test_adoption_preserves_original_work_and_dependencies_and_adds_only_a_gate(runtime):
    engine, backlog, _ = runtime
    first = backlog.register('kingdom', 'original-first', title='Inspect queue',
        description='Inspect the existing queue', priority=72, task_type='reliability')
    second = backlog.register('kingdom', 'original-second', title='Repair queue',
        description='Repair after inspection', depends_on=[first['id']], priority=64)
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.adopt('kingdom', 'adopt-original',
        [{'work_id': first['id'], 'expected_revision': first['revision']},
         {'work_id': second['id'], 'expected_revision': second['revision']}],
        title='Queue repair', source_revision='a'*40)
    assert state['auto_plan'] is False
    assert state['source_revision'] == 'a'*40
    assert state['planner_mode'] == 'deliberative' and state['planner_routing'] == 'local'
    section = state['sections'][0]
    assert [row['work_id'] for row in section['items']] == [first['id'], second['id']]
    assert section['integration']['work_id'] not in {first['id'], second['id']}
    assert len(backlog.list()) == 3
    for original in (first, second):
        saved = backlog.get('kingdom', original['id'])
        assert saved['intent'] == original['intent']
        assert saved['title'] == original['title'] and saved['description'] == original['description']
        assert saved['priority'] == original['priority']
        assert saved['revision'] == original['revision'] + 1
        assert saved['programme_id'] == state['id']
        assert saved['status'] == 'needs_planning' and saved['enabled'] is False
    gate = backlog.get('kingdom', section['integration']['work_id'])
    assert set(gate['intent']['depends_on']) == {first['id'], second['id']}
    assert gate['enabled'] is False and gate['intent']['mission_id'] is None
    assert section['status'] == 'unfinished'
    assert engine.tasks.list() == [] and engine.missions.list() == []


def test_identical_retry_after_restart_reuses_the_original_revision_binding(runtime):
    engine, backlog, _ = runtime
    note = backlog.register('kingdom', 'restart-original', title='Inspect restart')
    refs = [{'work_id': note['id'], 'expected_revision': note['revision']}]
    state = WorkProgrammes(backlog.db, engine, backlog).adopt('kingdom', 'restart-adopt', refs,
        title='Restart', source_revision='a'*40)
    assert backlog.get('kingdom', note['id'])['revision'] != refs[0]['expected_revision']
    restored = WorkProgrammes(backlog.db, engine, backlog)
    assert restored.adopt('kingdom', 'restart-adopt', refs,
        title='Restart', source_revision='a'*40)['id'] == state['id']
    with pytest.raises(ValueError, match='Idempotency'):
        restored.adopt('kingdom', 'restart-adopt', refs, title='Different', source_revision='a'*40)
    assert len(backlog.list()) == 2 and len(restored.list()) == 1


def test_adopted_note_enters_existing_planner_without_becoming_executable(runtime):
    import asyncio
    engine, backlog, _ = runtime
    note = backlog.register('kingdom', 'planner-original', title='Inspect cancellation',
        description='Inspect cancellation of queued model requests')
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.adopt('kingdom', 'planner-adopt', [{'work_id': note['id'], 'expected_revision': 1}],
        title='Cancellation', source_revision='a'*40, planner_mode='configured_chat')
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{"question":"Which model connection?"}'}))
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    row = state['sections'][0]['items'][0]
    assert row['work_id'] == note['id'] and row['planning'] == 'awaiting_answer'
    assert note['description'] in engine.models.plan_chat.await_args.args[0]
    assert len(backlog.list()) == 2
    saved = backlog.get('kingdom', note['id'])
    assert saved['enabled'] is False and saved['intent']['mission_id'] is None
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_reviewed_adopted_note_uses_native_acceptance_and_keeps_section_gate(runtime):
    import asyncio
    engine, backlog, _ = runtime
    note = backlog.register('kingdom', 'execution-original', title='Check component')
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.adopt('kingdom', 'execution-adopt', [{'work_id': note['id'], 'expected_revision': 1}],
        title='Component', source_revision='a'*40, planner_mode='configured_chat')
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': json.dumps({
        'plan': plan().model_dump(), 'acceptance_step': 'suite'})}))
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    state = service.approve(state['id'], 's1-t1', state['revision'])
    backlog.settings(True, backlog.snapshot()['revision'])
    backlog.tick()
    execute(engine)
    backlog.tick()
    accepted = backlog.get('kingdom', note['id'])
    assert accepted['status'] == 'completed' and accepted['evidence']['tests_run'] == 1
    saved = service.snapshot(state['id'])
    assert saved['sections'][0]['items'][0]['work_id'] == note['id']
    assert saved['sections'][0]['integration']['planning'] == 'unplanned'
    assert saved['sections'][0]['status'] == 'unfinished'
    assert len(backlog.list()) == 2 and len(engine.tasks.list()) == 1


@pytest.mark.parametrize('change', [
    {'status': 'running'}, {'status': 'completed'}, {'enabled': True},
    {'lease': {'token': 'retained'}}, {'evidence': {'tests_run': 1}}, {'revision': 2},
    {'intent': {'mission_id': 'bound', 'mission_version': 1, 'acceptance_step': 'test', 'depends_on': []}}])
def test_ineligible_second_note_leaves_the_whole_adoption_unchanged(runtime, change):
    engine, backlog, _ = runtime
    first = backlog.register('kingdom', 'atomic-first', title='First')
    second = backlog.register('kingdom', 'atomic-second', title='Second')
    altered = {**second, **change}
    # Fixture setup seeds persisted lifecycle states that must never be adopted.
    with backlog.db.get_connection() as conn:
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(altered), second['id']))
    service = WorkProgrammes(backlog.db, engine, backlog)
    with pytest.raises(ValueError):
        service.adopt('kingdom', 'atomic-adopt', [
            {'work_id': first['id'], 'expected_revision': 1},
            {'work_id': second['id'], 'expected_revision': 1}], title='Atomic', source_revision='a'*40)
    assert backlog.get('kingdom', first['id']) == first
    assert backlog.get('kingdom', second['id']) == altered
    assert len(backlog.list()) == 2 and service.list() == []


def test_storage_failure_rolls_back_gate_and_ownership_without_publishing(runtime):
    engine, backlog, _ = runtime
    note = backlog.register('kingdom', 'rollback-original', title='Rollback')
    service = WorkProgrammes(backlog.db, engine, backlog)
    published = []
    engine.events.publish = lambda *args: published.append(args)
    with backlog.db.get_connection() as conn:
        conn.execute("CREATE TRIGGER fail_programme_insert BEFORE INSERT ON work_programmes "
                     "BEGIN SELECT RAISE(ABORT,'fixture storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='fixture storage failure'):
        service.adopt('kingdom', 'rollback-adopt', [{'work_id': note['id'], 'expected_revision': 1}],
            title='Rollback', source_revision='a'*40)
    assert backlog.list() == [note] and service.list() == [] and published == []


def test_adoption_requires_a_closed_same_project_acyclic_dependency_set(runtime):
    engine, backlog, _ = runtime
    first = backlog.register('kingdom', 'graph-first', title='First')
    second = backlog.register('kingdom', 'graph-second', title='Second', depends_on=[first['id']])
    other = backlog.register('centipede', 'graph-other', title='Other project')
    service = WorkProgrammes(backlog.db, engine, backlog)
    for refs in ([{'work_id': second['id'], 'expected_revision': 1}],
                 [{'work_id': other['id'], 'expected_revision': 1}],
                 [{'work_id': first['id'], 'expected_revision': 1}]*2):
        with pytest.raises(ValueError):
            service.adopt('kingdom', 'graph-adopt', refs, title='Graph', source_revision='a'*40)
    # A corrupted retained cycle must fail closed instead of producing a gate.
    first['intent']['depends_on'] = [second['id']]
    with backlog.db.get_connection() as conn:
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(first), first['id']))
    with pytest.raises(ValueError, match='cycle'):
        service.adopt('kingdom', 'graph-adopt', [
            {'work_id': first['id'], 'expected_revision': 1}, {'work_id': second['id'], 'expected_revision': 1}],
            title='Graph', source_revision='a'*40)
    assert len(backlog.list()) == 3 and service.list() == []


def test_existing_programme_ownership_cannot_be_reused_even_without_a_note_marker(runtime):
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    original = service.create('kingdom', 'already-owned', '- Existing programme outcome')
    row = original['sections'][0]['items'][0]
    note = backlog.get('kingdom', row['work_id'])
    assert 'programme_id' not in note
    with pytest.raises(ValueError, match='unowned'):
        service.adopt('kingdom', 'steal-owned', [{'work_id': note['id'], 'expected_revision': note['revision']}],
            title='Another programme', source_revision='a'*40)
    assert len(backlog.list()) == 2 and len(service.list()) == 1


def test_two_processes_cannot_adopt_the_same_notes_into_different_programmes(runtime):
    engine, backlog, _ = runtime
    note = backlog.register('kingdom', 'race-original', title='Original')
    WorkProgrammes(backlog.db, engine, backlog)
    code = '''import json,sys,time
from types import SimpleNamespace
from pathlib import Path
from backend.storage.db import Database
from backend.runtime.work_backlog import WorkBacklog
from backend.runtime.work_programmes import WorkProgrammes
database=Database(sys.argv[1])
engine=SimpleNamespace(events=SimpleNamespace(publish=lambda *args:None))
queue=WorkBacklog(database,engine);service=WorkProgrammes(database,engine,queue)
Path(sys.argv[4]).write_text('ready')
while not Path(sys.argv[5]).exists():time.sleep(.01)
try:
 result=service.adopt('kingdom',sys.argv[3],[{'work_id':sys.argv[2],'expected_revision':1}],title='Race',source_revision='a'*40)
 print(json.dumps({'adopted':True,'id':result['id']}))
except ValueError:print(json.dumps({'adopted':False}))
'''
    import os
    import time
    root = Path(__file__).resolve().parents[1]
    start = backlog.db.db_path.parent/'race-start'
    children = []
    env = {**os.environ, 'PYTHONPATH': str(root)}
    try:
        for index in range(2):
            ready = start.with_name('race-ready-'+str(index))
            child = subprocess.Popen([sys.executable, '-c', code, str(backlog.db.db_path), note['id'],
                'race-'+str(index), str(ready), str(start)], cwd=root, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            children.append((child, ready))
        deadline = time.monotonic()+15
        while not all(ready.exists() for _, ready in children) and time.monotonic()<deadline:
            time.sleep(.02)
        assert all(ready.exists() for _, ready in children)
        start.write_text('go')
        results = []
        for child, _ in children:
            stdout, stderr = child.communicate(timeout=15)
            assert child.returncode == 0, stderr
            results.append(json.loads(stdout))
        assert sum(row['adopted'] for row in results) == 1
    finally:
        for child, _ in children:
            if child.poll() is None:
                child.kill(); child.communicate(timeout=5)
    assert len(backlog.list()) == 2
    assert len(WorkProgrammes(backlog.db, engine, backlog).list()) == 1
