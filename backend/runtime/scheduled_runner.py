"""Lifecycle-owned polling of durable, explicitly configured local schedules."""
import asyncio


class ScheduledRunner:
    def __init__(self, scheduled, engine, interval=30):
        self.scheduled, self.engine, self.interval = scheduled, engine, interval
        self.task = None
        self.stop_event = None

    async def start(self):
        if self.task and not self.task.done():
            return
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(self.run(), name='kingdom-durable-schedules')

    async def stop(self):
        if self.task:
            self.stop_event.set()
            await self.task
            self.task = None

    async def run(self):
        failed = False
        while not self.stop_event.is_set():
            try:
                policy = await asyncio.to_thread(self.engine.execution_policy.get)
                if policy['level'] > 0:
                    await asyncio.to_thread(self.scheduled.tick)
                    await asyncio.to_thread(self.scheduled.deliver)
                failed = False
            except Exception:
                if not failed:
                    self.engine.events.publish('automation.schedule_runner_error',
                        {'notice': 'Schedule polling failed; durable checkpoints retained.'})
                failed = True
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
