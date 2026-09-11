"""
Regression test for NodeRegistry public export contract.
Ensures NodeRegistry, NodeInfo, NodeStatus, NodeRole, and HardwareProfile remain importable and functioning.
"""

import unittest
from backend.cluster.node_registry import NodeRegistry, NodeInfo, NodeStatus, NodeRole, HardwareProfile

class TestNodeRegistryContract(unittest.TestCase):

    def test_node_registry_public_imports_and_types(self):
        registry = NodeRegistry()
        hw = HardwareProfile(cpu_cores=8, ram_gb=16, vram_gb=4)
        node = NodeInfo(
            node_id="test-node-01",
            hostname="test-host",
            role=NodeRole.KNIGHT,
            status=NodeStatus.CONNECTED,
            hardware_profile=hw,
            trust_score=0.95
        )

        reg_res = registry.register_node(node)
        self.assertEqual(reg_res["id"], "test-node-01")

        retrieved = registry.get_node("test-node-01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.node_id, "test-node-01")
        self.assertEqual(retrieved.role, "knight")

        registry.update_node_status("test-node-01", NodeStatus.QUARANTINED)
        active_nodes = registry.list_active_nodes()
        self.assertNotIn("test-node-01", [n.node_id for n in active_nodes])

if __name__ == "__main__":
    unittest.main()
