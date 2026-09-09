# Multi-Node Cluster Operations Guide

## System Overview

Kingdom v40.2 supports multi-node cluster federation across Commanders, Knights, and specialized workers.

---

## 1. Node Pairing & Discovery

1. **Generate Invitation Challenge:** Commander creates a single-use pairing code (`backend/cluster/pairing.py`).
2. **Node Request:** Joining node submits proof-of-possession Ed25519 signature challenge.
3. **Approval:** Commander approves node registration (`NodeRegistry.update_node_state(node_id, NodeState.APPROVED)`).

---

## 2. Cluster Monitoring & Diagnostics

- **List All Nodes:** Inspect active node states via Command Center UI (`/nodes`) or backend `NodeRegistry.list_nodes()`.
- **Heartbeat Timeout:** Nodes failing to report heartbeats for > 60 seconds automatically transition to `DISCONNECTED` state and active tasks are reassigned.

---

## 3. Node Revocation & Quarantine

To revoke a compromised or rogue node:

```python
from backend.cluster.partition_resilience import RevocationPropagator
from backend.cluster.node_registry import node_registry

propagator = RevocationPropagator(node_registry)
propagator.broadcast_revocation(
    revocation_target_id="node_compromised_key",
    target_type="node",
    reason="Security audit key compromise"
)
```

Revoked nodes are immediately transitioned to `REVOKED` state and blocked from future reconnections.
