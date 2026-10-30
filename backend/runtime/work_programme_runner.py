"""Kingdom-owned planning loop, independent of browser and slow task execution."""
import asyncio


class WorkProgrammeRunner:
    def __init__(self, service, publish, interval=10, name='programme'):
        self.service, self.publish, self.interval = service, publish, interval
        self.task = None
        self.name = name

    async def start(self):
        if self.task and not self.task.done():
            return
        # Recover before execution runners start. Never replay interrupted binding.
        await asyncio.to_thread(self.service().recover_startup)
        self.task = asyncio.create_task(self.run(), name=f'kingdom-{self.name}-review')

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def run(self):
        failed = False
        while True:
            try:
                await self.service().tick()
                failed = False
            except Exception:
                if not failed:
                    self.publish(f'{self.name}.runner_error', {'notice': 'Review paused for this cycle; saved checkpoints retained. Inspect the work list.'})
                failed = True
            await asyncio.sleep(self.interval)
