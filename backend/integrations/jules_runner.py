"""Supervised async runner for Jules background dispatch and polling."""

import asyncio


class JulesRunner:
    def __init__(self, service_factory, publish, interval=10):
        self.service_factory = service_factory
        self.publish = publish
        self.interval = interval
        self.task = None
        self.stopping = None

    async def start(self):
        if self.task and not self.task.done():
            return
        self.stopping = asyncio.Event()
        self.task = asyncio.create_task(self.run(), name="kingdom-jules-runner")

    async def stop(self):
        if self.task:
            self.stopping.set()
            await self.task
            self.task = None

    async def run(self):
        failed = False
        while not self.stopping.is_set():
            try:
                service = await asyncio.to_thread(self.service_factory)
                res = await asyncio.to_thread(service.tick)
                failed = False
            except Exception as error:
                if not failed:
                    self.publish(
                        "jules.runner_error",
                        {
                            "notice": "Jules polling runner failed. Inspect adapter settings and retained jobs.",
                            "error_type": type(error).__name__,
                        },
                    )
                failed = True
            try:
                await asyncio.wait_for(
                    self.stopping.wait(), timeout=self.interval
                )
            except asyncio.TimeoutError:
                pass
