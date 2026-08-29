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


if __name__ == "__main__":
    unittest.main()
