"""Service lifecycle and scheduler crash/restart regression tests.

Uses controlled background tasks: no cloud accounts, model stubs, or real side
effects. These tests assert ordering and absence of orphaned runner tasks.
"""
import asyncio
from types import SimpleNamespace

from backend.runtime.service_supervisor import RuntimeServiceSupervisor
from backend.runtime.scheduler import Scheduler


class FakeRunner:
    def __init__(self, name, seen, *, fail_start=False, fail_stop=False):
        self.name, self.seen = name, seen
        self.fail_start, self.fail_stop = fail_start, fail_stop
        self.task = None

    async def start(self):
        self.seen.append("start:" + self.name)
        self.task = asyncio.create_task(asyncio.Event().wait())
        if self.fail_start:
            raise RuntimeError("deliberate startup failure")

    async def stop(self):
        self.seen.append("stop:" + self.name)
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        if self.fail_stop:
            raise RuntimeError("deliberate shutdown failure")


class FakeEngine:
    def __init__(self, seen):
        self.seen = seen
        self.scheduler = SimpleNamespace(health=lambda: {"status": "stopped"})

    def autostart_requested(self):
        return True

    async def start(self, persist=True):
        self.seen.append("engine:start")

    async def stop(self, persist=True):
        self.seen.append("engine:stop")


def test_supervisor_reverses_partial_startup_even_if_failed_service_created_task():
    async def run():
        seen = []
        a = FakeRunner("a", seen)
        b = FakeRunner("b", seen, fail_start=True)
        supervisor = RuntimeServiceSupervisor(FakeEngine(seen), {"a": a, "b": b})
        try:
            await supervisor.start()
            assert False, "Expected startup to fail"
        except RuntimeError:
            pass
        assert supervisor.status()["state"] == "failed"
        assert not a.task and not b.task
        assert seen == ["engine:start", "start:a", "start:b",
                        "stop:b", "stop:a", "engine:stop"]
        await supervisor.stop()
    asyncio.run(run())


def test_supervisor_starts_once_and_stops_all_even_if_one_stop_fails():
    async def run():
        seen = []
        a = FakeRunner("a", seen, fail_stop=True)
        b = FakeRunner("b", seen)
        supervisor = RuntimeServiceSupervisor(FakeEngine(seen), {"a": a, "b": b})
        await supervisor.start()
        await supervisor.start()
        assert supervisor.status()["healthy"] is True
        await supervisor.stop()
        assert not a.task and not b.task
        assert supervisor.status()["state"] == "failed"
        assert supervisor.status()["cleanup_errors"] == ["RuntimeError"]
        assert seen == ["engine:start", "start:a", "start:b",
                        "stop:b", "stop:a", "engine:stop"]
    asyncio.run(run())


def test_scheduler_recovers_from_tick_error_and_reports_sanitized_health():
    async def run():
        finished = asyncio.Event()
        errors = []
        runs = []

        async def tick():
            runs.append(1)
            if len(runs) == 1:
                raise RuntimeError("sensitive data must not enter health")
            finished.set()

        scheduler = Scheduler(tick, interval_seconds=0.005,
                              on_error=lambda kind, count: errors.append((kind, count)))
        assert await scheduler.start() is True
        await asyncio.wait_for(finished.wait(), timeout=2)
        assert scheduler.running
        assert scheduler.health()["total_failures"] == 1
        assert scheduler.health()["consecutive_failures"] == 0
        assert errors == [("RuntimeError", 1)]
        assert "sensitive" not in repr(scheduler.health())
        assert await scheduler.stop() is True
        assert scheduler.health()["status"] == "stopped"
    asyncio.run(run())


def test_scheduler_stop_interrupts_backoff_after_repeated_failure():
    async def run():
        failed = asyncio.Event()

        async def tick():
            failed.set()
            raise OSError("transient database unavailable")

        scheduler = Scheduler(tick, interval_seconds=0.005)
        await scheduler.start()
        await failed.wait()
        await asyncio.wait_for(scheduler.stop(), timeout=1)
        assert not scheduler.running
        assert scheduler.health()["total_failures"] >= 1
    asyncio.run(run())
