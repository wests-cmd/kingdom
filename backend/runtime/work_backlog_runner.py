"""Lifecycle-owned backlog review, independent of slow scheduled model requests."""
import asyncio


class WorkBacklogRunner:
    def __init__(self, service, publish, interval=5):
        self.service, self.publish, self.interval = service, publish, interval
        self.task = None
        self.stopping = None

    async def start(self):
        if self.task and not self.task.done():
            return
        self.stopping = asyncio.Event()
        self.task = asyncio.create_task(self.run(), name='kingdom-work-backlog')

    async def stop(self):
        if self.task:
            self.stopping.set()
            await self.task
            self.task = None

    async def run(self):
        failed = False
        recovered = False
        while not self.stopping.is_set():
            try:
                service = await asyncio.to_thread(self.service)
                if not recovered:
                    await asyncio.to_thread(service.recover_startup)
                    recovered = True
                await asyncio.to_thread(service.tick)
                failed = False
            except Exception:
                if not failed:
                    self.publish('backlog.runner_error', {
                        'notice': 'Work-list review failed; saved work retained. Inspect the review queue.'})
                failed = True
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
