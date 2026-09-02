import unittest
from backend.runtime.engine import RuntimeEngine

class TestRuntimeEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RuntimeEngine()

    def test_runtime_start_stop_status(self):
        start_res = self.engine.start()
        self.assertEqual(start_res["status"], "started")

        status_res = self.engine.status()
        self.assertTrue(status_res["running"])
        self.assertEqual(status_res["mode"], "adaptive")

        stop_res = self.engine.stop()
        self.assertEqual(stop_res["status"], "stopped")
        self.assertFalse(self.engine.status()["running"])

if __name__ == "__main__":
    unittest.main()
