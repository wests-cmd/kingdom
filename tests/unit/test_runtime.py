import unittest
from backend.runtime.engine import RuntimeEngine
from backend.state import STATE

class TestRuntimeEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        STATE["mode"] = "adaptive"
        STATE["running"] = False
        self.engine = RuntimeEngine()

    async def test_runtime_start_stop_status(self):
        start_res = await self.engine.start()
        self.assertEqual(start_res["status"], "started")

        status_res = self.engine.status()
        self.assertTrue(status_res["running"])
        self.assertEqual(status_res["mode"], "adaptive")

        stop_res = await self.engine.stop()
        self.assertEqual(stop_res["status"], "stopped")
        self.assertFalse(self.engine.status()["running"])

if __name__ == "__main__":
    unittest.main()
