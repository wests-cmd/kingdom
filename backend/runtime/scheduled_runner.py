"""Lifecycle-owned polling of durable, explicitly configured local schedules."""
import asyncio


class ScheduledRunner:
    def __init__(self, scheduled, engine, interval=30, requests=None):
        self.scheduled, self.engine, self.interval = scheduled, engine, interval
        self.task = None
        self.stop_event = None
        self.requests = requests

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
                    if self.requests:
                        await self.execute_pending(policy['level'])
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

    async def execute_pending(self, level):
        """One bounded job at a time; request CAS and checkpoints prevent replay."""
        service = await asyncio.to_thread(self.requests)
        with self.scheduled.db.get_connection() as conn:
            rows = conn.execute("SELECT o.run_key,o.request_id,o.schedule_id,s.payload,s.status FROM durable_schedule_outbox o JOIN durable_schedules s ON s.id=o.schedule_id WHERE o.status='enqueued' ORDER BY o.rowid LIMIT 20").fetchall()
        import json
        for row in rows:
            request = await asyncio.to_thread(service.get, row['request_id'])
            payload = json.loads(row['payload'])
            if request['status'] == 'queued' and payload.get('autorun') and level >= 4 and row['status'] == 'active':
                request = await service.run(request['id'])
            status = request['status']
            if status == 'queued':
                continue
            with self.scheduled.db.get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if status in {'completed', 'cancelled'}:
                    outcome = 'execution_completed' if status == 'completed' else 'cancelled'
                else:
                    outcome = 'execution_needs_review'
                    conn.execute("UPDATE durable_schedules SET status='paused',revision=revision+1 WHERE id=?", (row['schedule_id'],))
                conn.execute('UPDATE durable_schedule_outbox SET status=? WHERE run_key=?', (outcome, row['run_key']))
                conn.commit()
