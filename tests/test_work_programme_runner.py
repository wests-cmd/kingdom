import asyncio
from backend.runtime.work_programme_runner import WorkProgrammeRunner
from test_project_test_missions import runtime


def test_programme_database_contention_does_not_block_network_event_loop(runtime):
    """A SQLite lock must not prevent RPC/revocation callbacks from running."""
    import sqlite3
    import threading
    import time
    from backend.runtime.work_programmes import WorkProgrammes

    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    locked = threading.Event()
    release = threading.Event()

    def writer():
        with sqlite3.connect(backlog.db.db_path) as conn:
            conn.execute('BEGIN EXCLUSIVE')
            locked.set()
            release.wait(1)  # Emergency cleanup also makes the unfixed test bounded.
            conn.commit()

    thread = threading.Thread(target=writer)
    thread.start()
    assert locked.wait(2)

    async def exercise():
        started = time.monotonic()
        callback_elapsed = []

        def network_callback():
            callback_elapsed.append(time.monotonic() - started)
            release.set()

        asyncio.get_running_loop().call_later(.02, network_callback)
        await service.tick()
        await asyncio.sleep(.03)
        assert callback_elapsed[0] < .5, 'Programme SQLite wait blocked the network event loop'

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()


def test_kingdom_loop_runs_without_browser_recovers_once_and_cancels_slow_planning():
    async def exercise():
        called = asyncio.Event()
        cancelled = asyncio.Event()
        history = []

        class Service:
            def recover_startup(self):
                history.append('recovered')

            async def tick(self):
                history.append('planned')
                called.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        runner = WorkProgrammeRunner(lambda: Service(), lambda *args: None)
        await runner.start()
        original = runner.task
        await runner.start()
        assert runner.task is original
        await asyncio.wait_for(called.wait(), 2)
        await asyncio.wait_for(runner.stop(), 2)
        assert cancelled.is_set()
        assert history == ['recovered', 'planned']
        await runner.stop()
    asyncio.run(exercise())


def test_planner_errors_are_generic_and_next_cycle_still_runs():
    async def exercise():
        recovered = asyncio.Event()
        notices, calls = [], []

        class Service:
            def recover_startup(self):
                pass

            async def tick(self):
                calls.append(1)
                if len(calls) == 1:
                    raise ValueError('secret provider token')
                recovered.set()

        runner = WorkProgrammeRunner(lambda: Service(), lambda *args: notices.append(args), interval=.001)
        await runner.start()
        await asyncio.wait_for(recovered.wait(), 2)
        await runner.stop()
        assert len(notices) == 1
        assert 'secret' not in str(notices)
        assert len(calls) >= 2
    asyncio.run(exercise())


def test_transient_planning_recovers_after_durable_backoff_without_approval(runtime, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.runtime.work_programmes import WorkProgrammes
    engine, backlog, _ = runtime
    clock = [1000.0]
    monkeypatch.setattr('backend.runtime.work_programmes.time', SimpleNamespace(time=lambda: clock[0]))
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=[
        TimeoutError('private endpoint token'), {'text': '{"question":"Which test suite?"}'}]))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'recover-planner', '- Verify recovery', planner_mode='configured_chat')
    service.configure(state['id'], True, state['revision'])
    asyncio.run(service.tick())
    row = service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning_failure']['category'] == 'model_unavailable'
    assert row['planning_failure']['retryable'] is True
    assert row['planning_failure']['retry_at'] == 1060.0
    assert 'private' not in str(row)
    # A new service instance must honour the persisted deadline.
    service = WorkProgrammes(backlog.db, engine, backlog)
    asyncio.run(service.tick())
    assert engine.models.plan_chat.await_count == 1
    clock[0] = 1060.0
    asyncio.run(service.tick())
    row = service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning'] == 'awaiting_answer' and row['planning_attempts'] == 2
    assert len(row['planning_failure_history']) == 1
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_transient_retry_budget_and_disabled_auto_plan_are_enforced(runtime, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.runtime.work_programmes import WorkProgrammes
    engine, backlog, _ = runtime
    clock = [1000.0]
    monkeypatch.setattr('backend.runtime.work_programmes.time', SimpleNamespace(time=lambda: clock[0]))
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=TimeoutError('secret')))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'retry-budget', '- Verify recovery', planner_mode='configured_chat')
    service.configure(state['id'], True, state['revision'])
    for _ in range(3):
        asyncio.run(service.tick()); clock[0] += 1000
    asyncio.run(service.tick())
    row = service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning_attempts'] == 3 and row['planning_failure']['retryable'] is False
    assert engine.models.plan_chat.await_count == 3
    assert engine.missions.list() == [] and engine.tasks.list() == []
    other = service.create('kingdom', 'paused-retry', '- Verify recovery', planner_mode='configured_chat')
    asyncio.run(service.plan_next(other['id'], other['revision']))
    clock[0] += 1000
    asyncio.run(service.tick())
    assert engine.models.plan_chat.await_count == 4


def test_invalid_contract_is_not_a_transient_failure(runtime):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.runtime.work_programmes import WorkProgrammes
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': 'Ready'}))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'invalid-contract-no-retry', '- Verify recovery', planner_mode='configured_chat')
    service.configure(state['id'], True, state['revision'])
    asyncio.run(service.tick()); asyncio.run(service.tick())
    row = service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning_failure']['retryable'] is False
    assert engine.models.plan_chat.await_count == 1


def test_provider_authentication_denial_does_not_retry_or_expose_response(runtime):
    import httpx
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.runtime.work_programmes import WorkProgrammes
    engine, backlog, _ = runtime
    error=httpx.HTTPStatusError('private token', request=httpx.Request('POST','https://example.test'),response=httpx.Response(403))
    engine.models=SimpleNamespace(plan_chat=AsyncMock(side_effect=error))
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','auth-no-retry','- Verify recovery',planner_mode='configured_chat')
    service.configure(state['id'],True,state['revision'])
    asyncio.run(service.tick());asyncio.run(service.tick())
    row=service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning_failure']['retryable'] is False
    assert 'private' not in str(row) and engine.models.plan_chat.await_count==1
