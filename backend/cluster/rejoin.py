import time
import random
from typing import Dict, Any, Optional
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.heartbeat import heartbeat_manager

class RejoinManager:
    def __init__(self, base_delay_seconds: float = 1.0, max_delay_seconds: float = 60.0, max_retries: int = 10):
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.max_retries = max_retries

    def calculate_backoff_delay(self, attempt: int) -> float:
        exponential = self.base_delay_seconds * (2 ** (attempt - 1))
        capped = min(exponential, self.max_delay_seconds)
        jitter = random.uniform(0, capped * 0.1)
        return capped + jitter

    def rejoin(self, node_id: str, expected_kingdom_id: Optional[str] = None) -> Dict[str, Any]:
        node = node_registry.get_node(node_id)
        if not node:
            return {"rejoined": False, "error": f"Node {node_id} not registered"}

        state_val = node.node_state
        if state_val in [NodeState.REVOKED.value, NodeState.REJECTED.value, NodeState.QUARANTINED.value]:
            return {"rejoined": False, "error": f"Cannot rejoin node in restricted state {state_val}"}

        # Target Kingdom Identity Binding Check
        target_k_id = node.kingdom_id
        if expected_kingdom_id and target_k_id and expected_kingdom_id != target_k_id:
            return {
                "rejoined": False,
                "error": f"Target Kingdom identity mismatch: Node belongs to {target_k_id}, attempted reconnect to {expected_kingdom_id}"
            }

        res = heartbeat_manager.ping(node_id)
        return {
            "rejoined": res.get("success", False),
            "node_id": node_id,
            "kingdom_id": target_k_id,
            "node_state": res.get("node_state")
        }

rejoin_manager = RejoinManager()
