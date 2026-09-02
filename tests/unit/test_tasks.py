import unittest
from backend.runtime.engine import RuntimeEngine

class TestTaskSystem(unittest.TestCase):

    def setUp(self):
        self.engine = RuntimeEngine()

    def test_task_crud_and_cancellation(self):
        task = self.engine.create_task("test_type", {"query": "sample_input"})
        self.assertIsNotNone(task["id"])
        self.assertEqual(task["status"], "queued")

        fetched = self.engine.get_task(task["id"])
        self.assertEqual(fetched["id"], task["id"])

        cancelled = self.engine.cancel_task(task["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["cancellation_requested"])

if __name__ == "__main__":
    unittest.main()
