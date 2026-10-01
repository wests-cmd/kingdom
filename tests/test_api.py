from tests.auth_support import owner_client
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.state import STATE

class TestKingdomAPI(unittest.TestCase):

    def setUp(self):
        self.client = owner_client(app)
        STATE["running"] = False
        STATE["mode"] = "adaptive"

    def test_status_endpoint(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("running", data)
        self.assertIn("mode", data)
        self.assertEqual(data["version"], "v1TAS")
        self.assertEqual(data["release_version"], STATE["version"])
        self.assertEqual(data["contract_version"], "1.4.0")
        self.assertEqual(data["protocol"], {"major": 1, "minor": 4})
        self.assertIn("filesystem.read", data["capabilities"])
        self.assertIn("process.execute", data["capabilities"])
        self.assertEqual(
            set(data["tasks"]),
            {"queued", "running", "completed", "failed", "cancelled"},
        )

    def test_start_endpoint(self):
        with owner_client(app) as client:
            response = client.post("/start")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "started")
            self.assertTrue(STATE["running"])

    def test_stop_endpoint(self):
        with owner_client(app) as client:
            client.post("/start")
            response = client.post("/stop")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "stopped")
            self.assertFalse(STATE["running"])

    def test_mode_endpoint(self):
        response = self.client.get("/mode")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"mode": "adaptive"})

    def test_compatibility_endpoint(self):
        response = self.client.get("/api/system/compatibility")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["kingdom_version"], "1.0.1")
        self.assertEqual(data["protocol_version"], "kingdom.cluster.v1")
        self.assertEqual(data["version"], "v1TAS")
        self.assertEqual(data["release_version"], STATE["version"])
        self.assertEqual(data["contract_version"], "1.4.0")
        self.assertEqual(data["protocol"], {"major": 1, "minor": 4})
        self.assertIn("process.execute", data["capabilities"])
        self.assertTrue(data["feature_flags"]["signed_rpc"])

    def test_version_sentinel_propagation(self):
        original_ver = STATE.get("version")
        try:
            STATE["version"] = "99.99.99-sentinel"
            res_ver = self.client.get("/api/system/version").json()
            self.assertEqual(res_ver["version"], "99.99.99-sentinel")

            res_compat = self.client.get("/api/system/compatibility").json()
            self.assertEqual(res_compat["kingdom_version"], "99.99.99-sentinel")

            res_status = self.client.get("/status").json()
            self.assertEqual(res_status["version"], "v1TAS")
            self.assertEqual(res_status["release_version"], "99.99.99-sentinel")
        finally:
            if original_ver:
                STATE["version"] = original_ver

    def test_full_scan_diagnostic_endpoint(self):
        response = self.client.get("/diagnostics/full-scan")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["status"], ["PASS", "WARNING", "FAIL"])
        self.assertTrue(len(data["checks"]) >= 4)

if __name__ == "__main__":
    unittest.main()
