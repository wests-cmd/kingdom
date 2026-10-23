import asyncio
from backend.runtime.work_programme_runner import WorkProgrammeRunner


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
