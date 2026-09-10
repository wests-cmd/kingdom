import time
import pytest
from backend.cluster.node_registry import NodeRegistry, NodeState, node_registry
from backend.cluster.task_leasing import TaskLeaseManager
from backend.cluster.capability_router import CapabilityRouter, CapabilityRoutingError
from backend.cluster.partition_resilience import PartitionEngine, RevocationPropagator
from backend.cluster.transport import RPCSecureTransport
from backend.cluster.identity import BaseNodeIdentity, KingdomIdentity, KnightIdentity


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


def test_scenario_a_unannounced_node_disappearance_and_lease_fencing():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)
    lease_mgr = TaskLeaseManager()

    # Register Node A and Node B
    registry.register_discovered_node({
        "id": "node_A",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy"
    })
    registry.register_discovered_node({
        "id": "node_B",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy"
    })

    # Issue lease for task_999 to Node A (fencing token 1)
    lease1 = lease_mgr.issue_lease("task_999", "node_A", "compute")
    assert lease1.fencing_token == 1

    # Node A disappears unannounced -> Heartbeat timeout causes DISCONNECTED
    registry.check_stale_heartbeats(timeout_seconds=0.1)
    time.sleep(0.15)
    registry.check_stale_heartbeats(timeout_seconds=0.1)

    assert registry.get_node("node_A").node_state == NodeState.DISCONNECTED.value

    # Reassign lease for task_999 to Node B (fencing token 2)
    lease2 = lease_mgr.issue_lease("task_999", "node_B", "compute")
    assert lease2.fencing_token == 2

    # Stale execution attempt using fencing token 1 fails
    with pytest.raises(PermissionError, match="Fencing token error"):
        lease_mgr.validate_lease_execution("task_999", "node_B", fencing_token=1)

    # Stale Node A execution attempt fails node mismatch
    with pytest.raises(PermissionError, match="Node mismatch"):
        lease_mgr.validate_lease_execution("task_999", "node_A", fencing_token=2)


def test_scenario_b_malicious_knight_capability_escalation():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)

    # Malicious Knight declares capability "planner.execute" in discovery, but granted_capabilities lacks "system.admin"
    registry.register_discovered_node({
        "id": "node_rogue",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy",
        "capabilities": ["planner.execute", "system.admin"],
        "granted_capabilities": ["planner.execute"]  # Granted capabilities controls!
    })

    router = CapabilityRouter(registry)

    # Routing request for system.admin rejects node_rogue
    with pytest.raises(CapabilityRoutingError, match="No eligible node found"):
        router.select_best_node("system.admin")


def test_scenario_c_network_partition_fail_closed_execution():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)
    partition_engine = PartitionEngine(registry, max_heartbeat_skew_sec=5.0)

    registry.register_discovered_node({
        "id": "node_partitioned",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy"
    })

    # Network partition detected
    now = time.time()
    partition_engine.detect_partition_and_isolate("node_partitioned", last_contact_timestamp=now - 20.0)

    # Isolated node is DISCONNECTED and cannot be selected by router
    router = CapabilityRouter(registry)
    with pytest.raises(CapabilityRoutingError):
        router.select_best_node("node.execute")


def test_scenario_d_rpc_anti_replay_protection():
    sender_ident = KnightIdentity("knight_sender")
    master_ident = KingdomIdentity()

    # Register sender node in global node_registry with public identity
    node_registry.register_discovered_node({
        "id": "knight_sender",
        "node_state": NodeState.CONNECTED.value,
        "public_identity": sender_ident.get_public_identity(),
        "kingdom_id": master_ident.node_id
    })

    sender_transport = RPCSecureTransport(node_identity=sender_ident)
    receiver_transport = RPCSecureTransport(node_identity=master_ident)

    msg = sender_transport.create_signed_message(
        target_id=master_ident.node_id,
        msg_type="heartbeat",
        payload={"status": "ok"}
    )

    # First verification succeeds
    res_first = receiver_transport.verify_and_unwrap_message(msg)
    assert res_first["valid"] is True

    # Replaying identical message fails (message ID already in processed set)
    res_replay = receiver_transport.verify_and_unwrap_message(msg)
    assert res_replay["valid"] is False
    assert "Replay attack detected" in res_replay["error"]


def test_scenario_e_revoked_node_reconnection_quarantine():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)
    propagator = RevocationPropagator(registry)
    partition_engine = PartitionEngine(registry)

    registry.register_discovered_node({
        "id": "node_compromised_key",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy"
    })

    # Revoke node
    propagator.broadcast_revocation("node_compromised_key", "node", "Compromised Ed25519 identity key")

    # Attempted reconnection raises PermissionError and preserves REVOKED state
    with pytest.raises(PermissionError, match="is REVOKED"):
        partition_engine.verify_reconnection_state(
            node_id="node_compromised_key",
            reported_version="40.2.0",
            reported_clock_time=time.time()
        )

    assert registry.get_node("node_compromised_key").node_state == NodeState.REVOKED.value
