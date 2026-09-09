# Step 17 — Multi-Node Resilience Architecture

## Overview

Kingdom's multi-node resilience engine protects cluster state against network partitions, stale node reconnections, and capability revocations.

---

## Partition Engine & Fail-Closed Isolation

`PartitionEngine` (`backend/cluster/partition_resilience.py`) monitors heartbeat contact intervals:
- **Partition Detection:** Contact timeouts exceeding `max_heartbeat_skew_sec` (30s) automatically transition node state to `DISCONNECTED`.
- **Fail-Closed Isolation:** `CapabilityRouter` excludes disconnected nodes from task routing.

---

## Reconnection Verification & State Reconciliation

When a disconnected node attempts reconnection (`verify_reconnection_state`):
1. **Revocation Check:** `REVOKED` nodes are permanently blocked from reconnecting.
2. **Version Verification:** Reconnecting nodes must match current runtime software versions (`40.2.0`).
3. **Clock Skew Check:** Reconnecting node timestamps exceeding max tolerance (300s) raise `ValueError`.
4. **State Transition:** Verified nodes transition back to `CONNECTED` state and refresh capability leases.

---

## Instant Revocation Propagation

`RevocationPropagator` (`backend/cluster/partition_resilience.py`) broadcasts capability, skill, identity, and node revocation signals across all cluster peers with immutable audit logging.
