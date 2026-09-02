import unittest
import time
from backend.cluster.node_registry import NodeRegistry
from backend.knights.base_knight import BaseKnight

class TestKnightSystem(unittest.TestCase):

    def setUp(self):
        self.registry = NodeRegistry()

    def test_knight_registration_and_heartbeat(self):
        k_data = {"id": "test-knight-1", "role": "coder", "capabilities": ["coder.execute"]}
        reg = self.registry.register(k_data)
        self.assertEqual(reg["id"], "test-knight-1")

        fetched = self.registry.get_knight("test-knight-1")
        self.assertEqual(fetched["role"], "coder")

        hb = self.registry.heartbeat("test-knight-1", health="healthy")
        self.assertIsNotNone(hb)

    def test_base_knight_execution_lifecycle(self):
        knight = BaseKnight("unit-tester", role="coder")
        res = knight.execute({"id": "task-101", "actor": {"id": "admin", "role": "admin", "verified": True}})
        self.assertEqual(res["status"], "completed")

if __name__ == "__main__":
    unittest.main()
