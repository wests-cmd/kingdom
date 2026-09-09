import time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from backend.cluster.node_registry import NodeRegistry, NodeState


class PartitionEvent(BaseModel):
    event_id: str
    affected_node_id: str
    is_partitioned: bool
    detected_at: float = Field(default_factory=time.time)
    reason: str


class PartitionEngine:

    def __init__(self, node_registry: NodeRegistry, max_heartbeat_skew_sec: float = 30.0):
        self.node_registry = node_registry
        self.max_skew = max_heartbeat_skew_sec
        self.partition_events: List[PartitionEvent] = []

    def detect_partition_and_isolate(self, node_id: str, last_contact_timestamp: float) -> bool:
        now = time.time()
        time_since_contact = now - last_contact_timestamp

        if time_since_contact > self.max_skew:
            # Network partition / isolation detected -> update node state to DISCONNECTED
            self.node_registry.update_node_state(
                node_id,
                NodeState.DISCONNECTED,
                reason=f"Network partition detected: No contact for {round(time_since_contact, 1)}s"
            )
            event = PartitionEvent(
                event_id=f"part_{time.time_ns()}",
                affected_node_id=node_id,
                is_partitioned=True,
                reason=f"Contact timeout ({round(time_since_contact, 1)}s)"
            )
            self.partition_events.append(event)
            return True

        return False

    def verify_reconnection_state(
        self,
        node_id: str,
        reported_version: str,
        reported_clock_time: float,
        max_clock_skew_sec: float = 300.0
    ) -> bool:
        node = self.node_registry.get_node(node_id)
        if not node:
            raise KeyError(f"Reconnecting node '{node_id}' not found in registry.")

        if node.get("node_state") == NodeState.REVOKED.value:
            raise PermissionError(f"Reconnection rejected: Node '{node_id}' is REVOKED.")

        # Version compatibility check
        if reported_version != node.get("software_version", "40.2.0"):
            raise ValueError(
                f"Protocol version mismatch on reconnection: Expected {node.get('software_version')}, got {reported_version}."
            )

        # Clock skew sanity check
        now = time.time()
        clock_skew = abs(now - reported_clock_time)
        if clock_skew > max_clock_skew_sec:
            raise ValueError(f"Reconnection clock skew error: Clock skew ({round(clock_skew, 1)}s) exceeds tolerance.")

        # Transition node state back to CONNECTED
        self.node_registry.update_node_state(node_id, NodeState.CONNECTED, reason="Reconnection verified successfully")
        return True


class RevocationPropagator:

    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
        self.revocation_log: List[Dict[str, Any]] = []

    def broadcast_revocation(
        self,
        revocation_target_id: str,
        target_type: str,  # "node", "skill", "capability", "identity"
        reason: str
    ) -> Dict[str, Any]:
        record = {
            "revocation_id": f"rev_{time.time_ns()}",
            "target_id": revocation_target_id,
            "target_type": target_type,
            "reason": reason,
            "timestamp": time.time(),
            "acknowledged_nodes": []
        }

        # If target is a node, immediately update registry state
        if target_type == "node":
            self.node_registry.update_node_state(
                revocation_target_id,
                NodeState.REVOKED,
                reason=reason
            )

        self.revocation_log.append(record)
        return record
