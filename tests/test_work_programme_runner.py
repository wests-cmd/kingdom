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
