import asyncio
import unittest

from fastapi.testclient import TestClient

from backend.main import app
from backend.runtime.engine import RuntimeEngine


class RuntimeCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_and_task_completion_emit_events(self):
        engine = RuntimeEngine()
        task = engine.submit_task("research resilient distributed systems", {"source": "test"})
        self.assertEqual(task["status"], "queued")
        await engine.start()
        await asyncio.sleep(0.15)
        completed = engine.tasks.get(task["id"])
        self.assertIsNotNone(completed)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["result"]["assigned_to"], "researcher")
        self.assertTrue(engine.status()["running"])
        self.assertEqual(engine.events.history(10)[-1]["type"], "task.completed")
        await engine.stop()
        self.assertFalse(engine.status()["running"])

    async def test_only_queued_tasks_can_be_cancelled(self):
        engine = RuntimeEngine()
        task = engine.submit_task("code a status page")
        cancelled = engine.cancel_task(task["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(engine.tasks.counts()["cancelled"], 1)

    async def test_failed_task_is_requeued_until_its_attempt_limit(self):
        engine = RuntimeEngine()
        task = engine.submit_task("retry this", {"max_attempts": 2})
        running = engine.tasks.claim_next()

        requeued = engine.tasks.retry_or_fail(running["id"], "temporary failure")
        self.assertEqual(requeued["status"], "queued")
        self.assertEqual(requeued["attempt"], 1)

        running = engine.tasks.claim_next()
        failed = engine.tasks.retry_or_fail(running["id"], "permanent failure")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["attempt"], 2)


class RuntimeApiTests(unittest.TestCase):
    def test_task_api_and_websocket_snapshot(self):
        client = TestClient(app)
        response = client.post("/tasks", json={"prompt": "code a health check"})

        self.assertEqual(response.status_code, 201)
        task_id = response.json()["id"]
        self.assertEqual(client.get(f"/tasks/{task_id}").json()["status"], "queued")

        websocket = client.websocket_connect("/ws")
        websocket.__enter__()
        try:
            self.assertEqual(websocket.receive_json()["type"], "runtime.snapshot")
        finally:
            websocket.__exit__(None, None, None)

    def test_mode_api_rejects_unknown_modes(self):
        client = TestClient(app)
        self.assertEqual(client.put("/mode", json={"mode": "burst"}).json(), {"mode": "burst"})
        self.assertEqual(client.put("/mode", json={"mode": "unknown"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
