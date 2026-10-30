"""Runtime-owned bounded assistance; no model call per tool or browser tick."""
import asyncio


class ConsultationRunner:
    def __init__(self, service, publish, interval=20):
        self.service, self.publish, self.interval, self.task = service, publish, interval, None

    async def start(self):
        if self.task and not self.task.done():
            return
        await asyncio.to_thread(self.service().store.recover_startup)
        self.task = asyncio.create_task(self.run(), name='kingdom-assistance')

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        await asyncio.to_thread(self.service().connection.cancel)

    async def run(self):
        failed = False
        while True:
            try:
                await self.service().tick()
                failed = False
            except Exception:
                if not failed:
                    self.publish('assistance.runner_error', {'notice': 'Advice held; inspect retained questions and connection status.'})
                failed = True
            await asyncio.sleep(self.interval)
