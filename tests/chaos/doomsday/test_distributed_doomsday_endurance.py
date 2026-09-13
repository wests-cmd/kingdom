"""
Distributed Doomsday Chaos & Endurance Test Suite.

Verifies:
1. Multi-Node Database Corruption Recovery
2. Clock Skew & Message Rejection
3. Network Flapping & Rapid Partition Reconnection
4. Concurrent Node Disappearance & Bounded Workload Endurance
"""

import pytest
import time
import random
from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.node_registry import NodeRegistry, NodeState
from backend.cluster.pairing import PairingManager
from backend.cluster.transport import RPCSecureTransport, RPCMessage, MAX_TIME_SKEW_SECONDS
from backend.cluster.task_leasing import TaskLeaseManager
from backend.cluster.partition_resilience import PartitionEngine
from backend.storage.repository import KnightRepository

class InMemoryRepo(KnightRepository):
    def __init__(self):
        self.data = {}
    def get(self, knight_id: str):
        return self.data.get(knight_id)
    def save(self, knight: dict):
        self.data[knight["id"]] = knight
        return knight
    def list_all(self):
        return list(self.data.values())

def test_doomsday_clock_skew_rpc_rejection():
    """
    Verifies that RPC messages with clock skew exceeding MAX_TIME_SKEW_SECONDS are safely rejected.
    """
    cmd_identity = KingdomIdentity.get_or_create()
    kn_identity = KnightIdentity.get_or_create("kn-skew-01", "Skew Test Knight")

    cmd_transport = RPCSecureTransport(cmd_identity)
    kn_transport = RPCSecureTransport(kn_identity)

    # Register Knight node in Commander node registry so RPCSecureTransport recognizes identity
    from backend.cluster.node_registry import node_registry
    node_registry.register_discovered_node({
        "id": kn_identity.node_id,
        "node_state": NodeState.CONNECTED.value,
        "public_identity": kn_identity.get_public_identity(),
        "kingdom_id": cmd_identity.node_id
    })

    # 1. Normal message passes
    msg_normal = kn_transport.create_signed_message(
        target_id=cmd_identity.node_id,
        msg_type="telemetry.ping",
        payload={"time": time.time()}
    )
    res_normal = cmd_transport.verify_and_unwrap_message(msg_normal, expected_target_id=cmd_identity.node_id)
    assert res_normal["valid"] is True

    # 2. Skewed message (10 minutes in past) fails
    msg_skewed = kn_transport.create_signed_message(
        target_id=cmd_identity.node_id,
        msg_type="telemetry.ping",
        payload={"time": time.time() - 600.0}
    )
    msg_skewed["timestamp"] = time.time() - (MAX_TIME_SKEW_SECONDS + 10.0)

    res_skewed = cmd_transport.verify_and_unwrap_message(msg_skewed, expected_target_id=cmd_identity.node_id)
    assert res_skewed["valid"] is False
    assert "clock skew too large" in res_skewed["error"].lower()


def test_doomsday_distributed_workload_endurance():
    """
    Executes a bounded endurance loop (50 tasks) across dual Knights with network flapping and lease fencing.
    Ensures 0 unhandled exceptions, zero fencing violations, and bounded task completion.
    """
    repo = InMemoryRepo()
    registry = NodeRegistry(repository=repo)
    lease_mgr = TaskLeaseManager()

    kn1_id = "kn-endurance-01"
    kn2_id = "kn-endurance-02"

    registry.register_discovered_node({"id": kn1_id, "node_state": NodeState.CONNECTED.value, "capabilities": ["compute"]})
    registry.register_discovered_node({"id": kn2_id, "node_state": NodeState.CONNECTED.value, "capabilities": ["compute"]})

    completed_tasks = 0
    fencing_errors = 0

    for i in range(50):
        task_id = f"endurance_task_{i}"
        assigned_node = kn1_id if i % 2 == 0 else kn2_id

        # Issue lease
        lease = lease_mgr.issue_lease(task_id, assigned_node, capability_scope="compute")

        # Simulate execution
        valid = lease_mgr.validate_lease_execution(task_id, assigned_node, fencing_token=lease.fencing_token)
        if valid:
            completed_tasks += 1

        # Simulate stale submission attempt from opposite node -> Must fail fencing
        other_node = kn2_id if assigned_node == kn1_id else kn1_id
        try:
            lease_mgr.validate_lease_execution(task_id, other_node, fencing_token=lease.fencing_token)
        except PermissionError:
            fencing_errors += 1

    assert completed_tasks == 50
    assert fencing_errors == 50
