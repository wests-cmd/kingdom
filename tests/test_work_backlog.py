import json
from types import SimpleNamespace

import pytest

from backend.runtime.work_backlog import WorkBacklog
from backend.storage.db import Database


@pytest.fixture
def setup(tmp_path, monkeypatch):
    (tmp_path / 'data').mkdir()
    monkeypatch.chdir(tmp_path)
    Database(tmp_path / 'data' / 'kingdom.db')
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    db = Database(tmp_path / 'backlog.db')
    from backend.runtime.missions import MissionService
    from backend.runtime.tasks import TaskManager
    from backend.storage.repository import TaskRepository
    engine = SimpleNamespace(events=SimpleNamespace(publish=lambda *args: None),
                             execution_policy=SimpleNamespace(get=lambda: {'level': 4}),
                             status=lambda: {'running': True}, tasks=TaskManager(TaskRepository(db)))
    engine.missions = MissionService(engine, db)
    calls = []
    def advance(ident, *, backlog_lease=None):
        calls.append(ident)
        return engine.missions.get(ident)
    monkeypatch.setattr(engine.missions, 'advance', advance)
    def mission(ident='mission', status='approved'):
        state = {'id': ident, 'version': 1, 'approved_version': 1, 'status': status,
                 'plan': {'missing_requirements': [], 'steps': [
                     {'id': 'source', 'kind': 'write_file', 'path': 'solution.py'},
                     {'id': 'read', 'kind': 'read_file', 'path': 'solution.py'},
                     {'id': 'accept', 'kind': 'function_check', 'repair_source': 'source',
                      'input_from': 'read', 'case_profile': 'bounded_batch_size.v1'}]}, 'steps': {}}
        from backend.runtime.bounded_function_tests import profile_hash
        state['plan']['steps'][2]['case_profile_sha256'] = profile_hash()
        engine.missions.save(state)
        return state
    queue = WorkBacklog(db, engine)
    return queue, engine, db, mission, calls


def register(queue, **extra):
    return queue.register('kingdom', 'key', mission_id='mission', mission_version=1,
                          acceptance_step='accept', enabled=True, **extra)


def activate(queue):
    queue.settings(True, queue.snapshot()['revision'])


def test_owner_can_disable_failed_selection_without_dismissing_review(setup):
    queue, engine, db, mission, calls = setup
    state = mission(); item = register(queue); activate(queue)
    state['status'] = 'needs_review'
    state['failure'] = 'Fixed acceptance failed'
    engine.missions.save(state)
    failed = queue.tick()
    assert failed['status'] == 'review_required'
    saved = queue.configure('kingdom', item['id'], False, failed['revision'])
    assert saved['enabled'] is False
    for key in ('status', 'reason', 'evidence', 'intent', 'lease'):
        assert saved[key] == failed[key]
    assert engine.missions.get(state['id'])['failure'] == 'Fixed acceptance failed'
    with pytest.raises(ValueError):
        queue.configure('kingdom', item['id'], True, saved['revision'])
    with pytest.raises(ValueError):
        queue.configure('kingdom', item['id'], False, failed['revision'])
    queue.tick()
    assert not calls and not engine.tasks.list()


def test_unplanned_owner_items_stay_visible_and_never_execute(setup):
    queue, engine, db, mission, calls = setup
    item = queue.register('kingdom', 'historical45', title='Remaining hardware acceptance',
                          description='Needs actual device evidence', priority=80)
    activate(queue)
    assert queue.tick()['status'] == 'idle'
    assert WorkBacklog(db, engine).get('kingdom', item['id'])['status'] == 'needs_planning'
    assert not calls
    with pytest.raises(ValueError):
        queue.configure('kingdom', item['id'], True, item['revision'])


def test_optin_runtime_and_policy_gate_execution(setup):
    queue, engine, db, mission, calls = setup
    mission(); register(queue)
    assert queue.tick()['status'] == 'stopped'
    activate(queue)
    engine.status = lambda: {'running': False}
    assert queue.tick()['status'] == 'stopped'
    engine.status = lambda: {'running': True}
    engine.execution_policy.get = lambda: {'level': 3}
    assert queue.tick()['status'] == 'stopped'
    assert not calls


def test_idempotency_and_project_dependencies_survive_restart(setup):
    queue, engine, db, mission, calls = setup
    mission(); first = register(queue)
    assert register(WorkBacklog(db, engine))['id'] == first['id']
    with pytest.raises(ValueError):
        register(queue, title='Different owner intent')
    with pytest.raises(ValueError):
        queue.register('other', 'key', depends_on=[first['id']], title='Other project')
    mission('dependent')
    second = queue.register('kingdom', 'second', mission_id='dependent', mission_version=1,
                            acceptance_step='accept', enabled=True, depends_on=[first['id']])
    activate(queue)
    queue.tick(limit=100)
    assert calls == ['mission']
    assert queue.get('kingdom', second['id'])['status'] == 'ready'
    assert 'Dependencies lack current accepted evidence' in queue.snapshot()['items'][1]['reason']


def test_stopped_worker_recovery_uses_same_mission_and_lease(setup, monkeypatch):
    queue, engine, db, mission, calls = setup
    mission(); item = register(queue); activate(queue)
    def interrupted(ident, *, backlog_lease=None):
        calls.append(ident)
        raise RuntimeError('Interrupted after possible submission')
    monkeypatch.setattr(engine.missions, 'advance', interrupted)
    with pytest.raises(RuntimeError):
        queue.tick()
    restarted = WorkBacklog(db, engine)
    restarted.clock = lambda: 10**15
    current = restarted.get('kingdom', item['id'])
    assert current['lease'] and restarted.tick()['status'] == 'recovery_required'
    assert calls == ['mission']
    with pytest.raises(ValueError):
        restarted.reconcile('kingdom', item['id'], current['revision'], 'wrong')
    resumed = restarted.reconcile('kingdom', item['id'], current['revision'], current['lease'])
    assert resumed['intent'] == item['intent'] and resumed['status'] == 'ready'
    monkeypatch.setattr(engine.missions, 'advance', lambda ident, **kwargs: engine.missions.get(ident))
    assert restarted.tick()['intent']['mission_id'] == 'mission'


def test_running_task_prevents_recovery(setup):
    queue, engine, db, mission, calls = setup
    state = mission(); item = register(queue)
    task = engine.tasks.create('Existing task', {})
    engine.tasks.claim_next()
    state['steps']['accept'] = {'task_id': task['id']}; engine.missions.save(state)
    with db.get_connection() as conn:
        item.update(lease='a' * 32)
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(item), item['id'])); conn.commit()
    with pytest.raises(ValueError, match='not stopped'):
        queue.reconcile('kingdom', item['id'], item['revision'], item['lease'])


def test_completed_model_or_missing_receipt_cannot_complete_backlog(setup):
    queue, engine, db, mission, calls = setup
    mission(status='completed'); item = register(queue); activate(queue)
    result = queue.tick()
    assert result['status'] == 'review_required' and result['evidence'] is None
    assert queue.findings()[0]['status'] == 'proposed_for_review'
    assert queue.get('kingdom', item['id'])['status'] != 'completed'


def test_actual_native_acceptance_receipt_can_complete_once(setup):
    queue, engine, db, mission, calls = setup
    from backend.runtime.bounded_function_tests import check_function, TOOL
    from backend.runtime.computer_tools import write_file, read_file, receipt
    from backend.swarm.manager import execution_request
    source = 'def bounded_batch_size(requested, pending, hard_limit):\n    return max(0, min(requested, pending, hard_limit))\n'
    state = mission(status='completed')
    for step, tool, params, handler in [
        ('source', 'workspace.write@1.0.0', {'path': 'solution.py', 'content': source}, write_file),
        ('read', 'workspace.read@1.0.0', {'path': 'solution.py'}, read_file),
        ('accept', TOOL, {'source': source, 'profile_id': 'bounded_batch_size.v1'}, check_function),
    ]:
        metadata = {'tool': tool, 'tool_parameters': params, 'mission_id': 'mission',
                    'mission_version': 1, 'step_id': step, 'max_attempts': 1}
        task = engine.tasks.create('Execute ' + step, metadata)
        assert engine.tasks.claim_next()['id'] == task['id']
        task = engine.tasks.get(task['id']); child = execution_request(task, task['prompt'])
        output = handler(params)
        outcome = {'kind': 'native_tool', 'tool': tool, 'output': output, **receipt(child, output)}
        result = {'plan': {'task_id': task['id'], 'subtasks': [{'prompt': task['prompt'], 'knight': 'coder'}]},
                  'results': [{'knight': 'coder', 'status': 'completed', 'verification': {'state': 'VERIFIED'}, 'outcome': outcome}]}
        engine.tasks.complete(task['id'], result)
        state['steps'][step] = {'task_id': task['id']}
    engine.missions.save(state)
    register(queue); activate(queue)
    result = queue.tick()
    assert result['status'] == 'completed'
    assert result['evidence']['source_sha256'] == output['source_sha256']
    assert result['evidence']['cases_run'] > 0
    assert WorkBacklog(db, engine).tick()['status'] == 'idle'
    assert calls == ['mission']
    write_file({'path': 'solution.py', 'content': source + '\n# changed after acceptance\n'})
    assert queue.review()['items'][0]['status'] == 'review_required'


def test_current_failure_findings_deduplicate_and_never_execute_new_work(setup):
    queue, engine, db, mission, calls = setup
    state = mission(); register(queue)
    state.update(status='needs_review', failure='Repair budget exhausted', repair_history=[{'failed_task_id': 'existing'}])
    state['plan']['missing_requirements'] = ['Actual device permission unavailable']
    engine.missions.save(state)
    first = queue.review(); second = WorkBacklog(db, engine).review()
    assert len(first['findings']) == len(second['findings']) == 1
    assert first['findings'][0]['provenance']['repair_attempts'] == 1
    assert first['findings'][0]['provenance']['missing_requirements']
    assert not calls


def test_owner_note_attaches_only_exact_reviewed_mission(setup):
    queue, engine, db, mission, calls = setup
    item = queue.register('kingdom', 'note', title='Pending coding acceptance')
    mission()
    with pytest.raises(ValueError):
        queue.attach('kingdom', item['id'], 'mission', 2, 'accept', item['revision'])
    linked = queue.attach('kingdom', item['id'], 'mission', 1, 'accept', item['revision'])
    assert linked['status'] == 'paused' and not linked['enabled']


def test_model_step_and_unapproved_mission_cannot_be_registered(setup):
    queue, engine, db, mission, calls = setup
    state = mission()
    state['plan']['steps'][2]['kind'] = 'model'
    engine.missions.save(state)
    with pytest.raises(ValueError, match='native function'):
        register(queue)
    state = mission(); state['approved_version'] = None; engine.missions.save(state)
    with pytest.raises(ValueError, match='owner-reviewed'):
        register(queue)
    assert queue.snapshot()['items'] == []


def test_one_mission_cannot_be_registered_under_another_idempotency_key(setup):
    queue, engine, db, mission, calls = setup
    mission(); register(queue)
    with pytest.raises(ValueError, match='already tracked'):
        queue.register('kingdom', 'duplicate', mission_id='mission', mission_version=1, acceptance_step='accept')


def test_paused_level_three_tick_still_derives_review_findings(setup):
    queue, engine, db, mission, calls = setup
    state = mission(); register(queue)
    state.update(status='needs_review', failure='Actual failed checkpoint')
    engine.missions.save(state)
    engine.execution_policy.get = lambda: {'level': 3}
    assert queue.tick()['status'] == 'stopped'
    assert len(queue.findings()) == 1
    assert not calls


def pure_checkpoint(setup):
    queue, engine, db, mission, calls = setup
    from backend.runtime.computer_tools import write_file, read_file, receipt
    from backend.swarm.manager import execution_request
    write_file({'path': 'solution.py', 'content': 'Owner-reviewed source data'})
    state = mission()
    metadata = {'tool': 'workspace.read@1.0.0', 'tool_parameters': {'path': 'solution.py'},
                'mission_id': 'mission', 'mission_version': 1, 'step_id': 'read', 'max_attempts': 1}
    task = engine.tasks.create('Read source checkpoint', metadata)
    assert engine.tasks.claim_next()['id'] == task['id']
    task = engine.tasks.get(task['id']); child = execution_request(task, task['prompt'])
    output = read_file(metadata['tool_parameters'])
    outcome = {'kind': 'native_tool', 'tool': metadata['tool'], 'output': output, **receipt(child, output)}
    engine.tasks.complete(task['id'], {'plan': {'task_id': task['id'], 'subtasks': [{'prompt': task['prompt'], 'knight': 'coder'}]},
        'results': [{'knight': 'coder', 'status': 'completed', 'verification': {'state': 'VERIFIED'}, 'outcome': outcome}]})
    state['steps']['read'] = {'task_id': task['id']}; engine.missions.save(state)
    item = register(queue)
    item.update(lease='b' * 32, lease_owner=queue._owner_proof(), status='running')
    # Same PID with a different creation time proves this prior incarnation is gone.
    item['lease_owner']['process_created'] -= 100
    with db.get_connection() as conn:
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(item), item['id'])); conn.commit()
    return item, task


def test_startup_recovers_proven_stopped_pure_receipts_without_replay(setup):
    queue, engine, db, mission, calls = setup
    item, task = pure_checkpoint(setup)
    restarted = WorkBacklog(db, engine)
    recovered = restarted.recover_startup()
    assert recovered['recovered'] == [item['id']] and not recovered['review_required']
    current = restarted.get('kingdom', item['id'])
    assert current['lease'] is None and current['status'] == 'ready'
    assert current['recovery']['verified_task_ids'] == [task['id']]
    assert current['intent'] == item['intent']
    assert not calls
    assert restarted.recover_startup()['recovered'] == []


def test_real_exited_controller_process_is_proved_stopped(setup):
    import subprocess
    import sys
    queue, engine, db, mission, calls = setup
    item, task = pure_checkpoint(setup)
    # Actual owned child exits normally; no live service or worker is killed.
    stopped = json.loads(subprocess.check_output([sys.executable, '-c',
        'import os,psutil,json; print(json.dumps({"pid":os.getpid(),"process_created":psutil.Process().create_time()}))'], text=True))
    item['lease_owner'].update(stopped)
    with db.get_connection() as conn:
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(item), item['id'])); conn.commit()
    restarted = WorkBacklog(db, engine)
    assert restarted.recover_startup()['recovered'] == [item['id']]
    assert engine.tasks.get(task['id'])['status'] == 'completed'
    assert not calls


@pytest.mark.parametrize('ambiguous', ['alive_owner', 'legacy_owner', 'foreign_host', 'wrong_version',
                                        'running_task', 'missing_task', 'write_task', 'repair', 'tampered_receipt'])
def test_startup_retains_ambiguous_or_side_effect_lease(setup, ambiguous):
    queue, engine, db, mission, calls = setup
    item, task = pure_checkpoint(setup)
    state = engine.missions.get('mission')
    if ambiguous == 'alive_owner': item['lease_owner'] = queue._owner_proof()
    elif ambiguous == 'legacy_owner': item.pop('lease_owner')
    elif ambiguous == 'foreign_host': item['lease_owner']['host'] = 'different-computer'
    elif ambiguous == 'wrong_version': state['version'] = 2
    elif ambiguous == 'missing_task': state['steps']['read']['task_id'] = 'missing'
    elif ambiguous == 'repair': state['repair'] = {'phase': 'unknown'}
    elif ambiguous in {'running_task', 'write_task', 'tampered_receipt'}:
        saved = engine.tasks.get(task['id'])
        if ambiguous == 'running_task': saved['status'] = 'running'
        elif ambiguous == 'write_task': saved['metadata']['tool'] = 'workspace.write@1.0.0'
        else: saved['result']['results'][0]['outcome']['output']['text'] = 'forged'
        with db.get_connection() as conn:
            if ambiguous == 'running_task': conn.execute('UPDATE tasks SET status=? WHERE id=?', (saved['status'], saved['id']))
            elif ambiguous == 'write_task': conn.execute('UPDATE tasks SET metadata_json=? WHERE id=?', (json.dumps(saved['metadata']), saved['id']))
            else: conn.execute('UPDATE tasks SET result_json=? WHERE id=?', (json.dumps(saved['result']), saved['id']))
            conn.commit()
        engine.tasks.load_persisted_tasks()
    engine.missions.save(state)
    with db.get_connection() as conn:
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(item), item['id'])); conn.commit()
    restarted = WorkBacklog(db, engine)
    assert restarted.recover_startup()['review_required'] == [item['id']]
    assert restarted.get('kingdom', item['id'])['lease'] == item['lease']
    assert not calls


def test_api_requires_owner_and_rejects_extra_authority_fields():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.runtime.work_backlog_api import router, Item
    from pydantic import ValidationError
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/work-backlog').status_code in {401, 403, 503}
        assert client.get('/work-backlog/type-priorities').status_code in {401, 403, 503}
        assert client.put('/work-backlog/type-priorities', json={'priorities': {'security': 100}, 'expected_revision': 1}).status_code in {401, 403, 503}
        assert client.post('/work-backlog/settings', json={'enabled': True, 'expected_revision': 1}).status_code in {401, 403, 503}
    with pytest.raises(ValidationError):
        Item(idempotency_key='k', title='No authority escalation', grant_process=True)


def test_type_priority_orders_eligible_work_without_skipping_dependencies(setup):
    queue,engine,db,mission,calls=setup
    for name in ('normal','urgent','dependent'): mission(name)
    normal=queue.register('kingdom','normal',mission_id='normal',mission_version=1,acceptance_step='accept',enabled=True,priority=99)
    queue.register('kingdom','urgent',mission_id='urgent',mission_version=1,acceptance_step='accept',enabled=True,priority=1,task_type='security')
    queue.register('kingdom','dependent',mission_id='dependent',mission_version=1,acceptance_step='accept',enabled=True,task_type='critical',depends_on=[normal['id']])
    config=queue.type_priorities()
    saved=queue.set_type_priorities({'security':80,'critical':100},config['revision'])
    assert WorkBacklog(db,engine).type_priorities()==saved
    activate(queue)
    queue.tick()
    assert calls==['urgent']
    with pytest.raises(ValueError): queue.set_type_priorities({},config['revision'])


def test_type_priority_never_enables_paused_or_unplanned_work(setup):
    queue,engine,db,mission,calls=setup
    queue.register('kingdom','note',task_type='security')
    mission('paused')
    queue.register('kingdom','paused',mission_id='paused',mission_version=1,acceptance_step='accept',enabled=False,task_type='security')
    queue.set_type_priorities({'security':100},1)
    activate(queue)
    assert queue.tick()['status']=='idle' and not calls
    engine.execution_policy.get=lambda:{'level':3}
    assert queue.tick()['status']=='stopped'


@pytest.mark.parametrize('priorities',[{'security':True},{'security':101},{'security':-1},{'bad type':50},dict((str(n),1) for n in range(21))])
def test_type_priority_settings_are_bounded(setup,priorities):
    queue,*_=setup
    with pytest.raises(ValueError): queue.set_type_priorities(priorities,1)
    assert queue.type_priorities()=={'revision':1,'priorities':{}}
