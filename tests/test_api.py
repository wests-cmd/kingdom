import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.state import STATE

class TestKingdomAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        STATE["running"] = False
        STATE["mode"] = "adaptive"

    def test_status_endpoint(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("running", data)
        self.assertIn("mode", data)
        self.assertIn("version", data)

    def test_start_endpoint(self):
        with TestClient(app) as client:
            response = client.post("/start")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "started")
            self.assertTrue(STATE["running"])

    def test_stop_endpoint(self):
        with TestClient(app) as client:
            client.post("/start")
            response = client.post("/stop")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "stopped")
            self.assertFalse(STATE["running"])

    def test_mode_endpoint(self):
        response = self.client.get("/mode")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"mode": "adaptive"})

if __name__ == "__main__":
    unittest.main()
