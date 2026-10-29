"""Real mission dispatch and process receipts across independent backlog work."""
from test_project_test_missions import runtime, plan, execute
import sys
from backend.runtime.work_backlog import WorkBacklog


def register(engine, queue, key, priority=50, dependencies=None, test_plan=None):
    mission = engine.missions.create(test_plan or plan())
    mission = engine.missions.approve(mission['id'], 1)
    return queue.register('kingdom', key, mission_id=mission['id'], mission_version=1,
        acceptance_step='suite', enabled=True, priority=priority, depends_on=dependencies)


def test_waiting_high_priority_mission_does_not_starve_unrelated_ready_work(runtime):
    engine, queue, _ = runtime
    engine.execution_policy.get()['mission_budget']['max_parallel'] = 3
    first = register(engine, queue, 'first', priority=100)
    second = register(engine, queue, 'second', priority=1)
    queue.settings(True, queue.snapshot()['revision'])
    queue.tick()
    assert len(engine.tasks.list()) == 1
    queue.tick()
    queue.tick()
    assert len(engine.tasks.list()) == 2
    assert {task['metadata']['mission_id'] for task in engine.tasks.list()} == {
        first['intent']['mission_id'], second['intent']['mission_id']}


def test_completed_dependency_advances_next_with_real_receipt_and_restart_no_duplicate(runtime):
    engine, queue, _ = runtime
    first = register(engine, queue, 'first')
    second = register(engine, queue, 'second', dependencies=[first['id']])
    queue.settings(True, queue.snapshot()['revision'])
    queue.tick()
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', first['id'])['status'] == 'completed'
    queue = WorkBacklog(queue.db, engine)
    queue.recover_startup()
    queue.tick()
    assert len(engine.tasks.list()) == 2
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', second['id'])['status'] == 'completed'
    for _ in range(3): queue.tick()
    assert len(engine.tasks.list()) == 2


def test_many_ready_items_cannot_starve_finished_running_acceptance_after_restart(runtime):
    engine, queue, _ = runtime
    engine.execution_policy.get()['mission_budget']['max_parallel'] = 3
    first = register(engine, queue, 'first', priority=1)
    queue.settings(True, queue.snapshot()['revision'])
    queue.tick()
    execute(engine)
    for i in range(8): register(engine, queue, f'next-{i}', priority=100)
    queue = WorkBacklog(queue.db, engine)
    queue.recover_startup()
    queue.tick()
    assert queue.get('kingdom', first['id'])['status'] == 'completed'
    assert len(engine.tasks.list()) == 1


def test_owner_parallel_budget_one_holds_second_mission_until_first_accepted(runtime):
    engine, queue, _ = runtime
    first = register(engine, queue, 'first')
    second = register(engine, queue, 'second')
    queue.settings(True, queue.snapshot()['revision'])
    for _ in range(4): queue.tick()
    assert len(engine.tasks.list()) == 1
    assert queue.get('kingdom', second['id'])['status'] == 'ready'
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', first['id'])['status'] == 'completed'
    queue.tick()
    assert len(engine.tasks.list()) == 2
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', second['id'])['status'] == 'completed'
    for _ in range(3): queue.tick()
    assert len(engine.tasks.list()) == 2


def test_real_failed_suite_does_not_block_unrelated_ready_work(runtime):
    engine, queue, _ = runtime
    first = register(engine, queue, 'bad', priority=100,
        test_plan=plan(argv=[sys.executable, '-m', 'unittest', 'missing_suite']))
    queue.settings(True, queue.snapshot()['revision'])
    queue.tick()
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', first['id'])['status'] == 'review_required'
    second = register(engine, queue, 'second', priority=1)
    queue.tick()
    execute(engine)
    queue.tick()
    assert queue.get('kingdom', second['id'])['status'] == 'completed'
    assert len(engine.tasks.list()) == 2
