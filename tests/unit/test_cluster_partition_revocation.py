import time
import pytest
from backend.cluster.node_registry import NodeRegistry, NodeState
from backend.cluster.partition_resilience import PartitionEngine, RevocationPropagator


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


def test_partition_engine_detection_and_reconnection():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)

    registry.register_discovered_node({
        "id": "node_worker_1",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy",
        "software_version": "40.2.0"
    })

    partition_engine = PartitionEngine(registry, max_heartbeat_skew_sec=10.0)

    # 1. Contact within skew threshold -> No partition
    now = time.time()
    partitioned = partition_engine.detect_partition_and_isolate("node_worker_1", last_contact_timestamp=now - 5.0)
    assert partitioned is False

    # 2. Contact timeout (15s > 10s skew threshold) -> Partition detected, node DISCONNECTED
    partitioned_timeout = partition_engine.detect_partition_and_isolate("node_worker_1", last_contact_timestamp=now - 15.0)
    assert partitioned_timeout is True
    assert registry.get_node("node_worker_1")["node_state"] == NodeState.DISCONNECTED.value

    # 3. Valid Reconnection verification
    verified = partition_engine.verify_reconnection_state(
        node_id="node_worker_1",
        reported_version="40.2.0",
        reported_clock_time=now
    )
    assert verified is True
    assert registry.get_node("node_worker_1")["node_state"] == NodeState.CONNECTED.value

    # 4. Reconnection with excessive clock skew fails
    with pytest.raises(ValueError, match="clock skew error"):
        partition_engine.verify_reconnection_state(
            node_id="node_worker_1",
            reported_version="40.2.0",
            reported_clock_time=now - 1000.0  # 1000s skew!
        )


def test_revocation_propagator():
    repo = DummyRepo()
    registry = NodeRegistry(repository=repo)

    registry.register_discovered_node({
        "id": "node_compromised",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy"
    })

    propagator = RevocationPropagator(registry)

    # Broadcast revocation for node_compromised
    record = propagator.broadcast_revocation(
        revocation_target_id="node_compromised",
        target_type="node",
        reason="Security audit compromise"
    )

    assert record["target_id"] == "node_compromised"
    assert registry.get_node("node_compromised")["node_state"] == NodeState.REVOKED.value

    # Reconnection of revoked node is rejected
    partition_engine = PartitionEngine(registry)
    with pytest.raises(PermissionError, match="is REVOKED"):
        partition_engine.verify_reconnection_state(
            node_id="node_compromised",
            reported_version="40.2.0",
            reported_clock_time=time.time()
        )
