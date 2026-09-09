import time
import pytest
from backend.cluster.node_registry import NodeRegistry, NodeState
from backend.cluster.task_leasing import TaskLeaseManager
from backend.cluster.capability_router import CapabilityRouter, CapabilityRoutingError


class DummyRepo:
    def __init__(self):
        self.data = {}
    def get(self, k_id):
        return self.data.get(k_id)
    def save(self, item):
        self.data[item["id"]] = item
        return item
    def list_all(self):
        return list(self.data.values())


def test_task_lease_manager_fencing_and_expiration():
    mgr = TaskLeaseManager(default_lease_ttl_sec=0.2)

    # 1. Issue initial lease to Node A
    lease1 = mgr.issue_lease("task_100", "node_A", "compute.gpu")
    assert lease1.fencing_token == 1
    assert lease1.assigned_node_id == "node_A"

    # 2. Valid execution
    assert mgr.validate_lease_execution("task_100", "node_A", fencing_token=1) is True

    # 3. Node mismatch attempt raises PermissionError
    with pytest.raises(PermissionError, match="Node mismatch"):
        mgr.validate_lease_execution("task_100", "node_B", fencing_token=1)

    # 4. Issue new lease to Node B -> increments fencing token to 2
    lease2 = mgr.issue_lease("task_100", "node_B", "compute.gpu")
    assert lease2.fencing_token == 2

    # Stale execution attempt using old fencing token 1 fails
    with pytest.raises(PermissionError, match="Fencing token error"):
        mgr.validate_lease_execution("task_100", "node_B", fencing_token=1)

    # Valid execution on Node B with active fencing token 2
    assert mgr.validate_lease_execution("task_100", "node_B", fencing_token=2) is True

    # 5. Lease expiration test
    time.sleep(0.25)
    with pytest.raises(PermissionError, match="has expired"):
        mgr.validate_lease_execution("task_100", "node_B", fencing_token=2)


def test_capability_router_node_selection():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)

    # Register 2 nodes: Node Local and Node GPU Worker
    registry.register_discovered_node({
        "id": "node_local",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy",
        "is_local": True,
        "capabilities": ["planner.execute", "data.read"],
        "granted_capabilities": ["planner.execute", "data.read"],
        "hardware_profile": {"cpu_cores": 8, "vram_mb": 0}
    })

    registry.register_discovered_node({
        "id": "node_gpu_worker",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy",
        "is_local": False,
        "capabilities": ["model.inference", "coder.execute"],
        "granted_capabilities": ["model.inference", "coder.execute"],
        "hardware_profile": {"cpu_cores": 16, "vram_mb": 16384}
    })

    router = CapabilityRouter(registry)

    # 1. Route GPU inference task
    best_gpu = router.select_best_node("model.inference", min_vram_mb=8192)
    assert best_gpu["id"] == "node_gpu_worker"

    # 2. Data locality local_only policy enforcement
    best_local = router.select_best_node("data.read", data_locality="local_only")
    assert best_local["id"] == "node_local"

    # 3. Requesting local_only on non-local capability raises CapabilityRoutingError
    with pytest.raises(CapabilityRoutingError, match="No eligible node found"):
        router.select_best_node("coder.execute", data_locality="local_only")
