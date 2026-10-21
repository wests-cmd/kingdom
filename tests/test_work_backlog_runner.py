import asyncio
from backend.runtime.work_backlog_runner import WorkBacklogRunner


def test_lifecycle_reviews_without_browser_and_stops_without_another_tick():
    async def exercise():
        observed = asyncio.Event()
        loop = asyncio.get_running_loop()
        calls = []

        class Service:
            def recover_startup(self):
                calls.append('recovered')

            def tick(self):
                calls.append('reviewed')
                loop.call_soon_threadsafe(observed.set)

        runner = WorkBacklogRunner(lambda: Service(), lambda *args: None, interval=60)
        await runner.start()
        first = runner.task
        await runner.start()
        assert runner.task is first
        await asyncio.wait_for(observed.wait(), timeout=2)
        await asyncio.wait_for(runner.stop(), timeout=2)
        assert calls == ['recovered', 'reviewed']
        assert runner.task is None
        await runner.stop()
    asyncio.run(exercise())


def test_failure_is_visible_without_exception_text_or_losing_future_reviews():
    async def exercise():
        observed = asyncio.Event()
        loop = asyncio.get_running_loop()
        notices = []

        class Service:
            def recover_startup(self):
                pass

            def tick(self):
                loop.call_soon_threadsafe(observed.set)
                raise RuntimeError('private provider password must not be exposed')

        runner = WorkBacklogRunner(lambda: Service(), lambda *args: notices.append(args), interval=60)
        await runner.start()
        await asyncio.wait_for(observed.wait(), timeout=2)
        await asyncio.wait_for(runner.stop(), timeout=2)
        assert len(notices) == 1
        assert notices[0][0] == 'backlog.runner_error'
        assert 'password' not in str(notices)
    asyncio.run(exercise())
