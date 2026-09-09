# Step 16 & Step 17 Testing & Verification Strategy

## Overview

Kingdom v40.2 verifies multi-node distributed runtime resilience and partition safety through comprehensive unit, integration, and distributed chaos test suites.

---

## Test Inventory & Execution Commands

| Test Suite | Focus Area | Test Count | Execution Command |
|---|---|---|---|
| `tests/test_distributed_chaos_scenarios.py` | Distributed chaos scenarios (node disappearance, fencing token checks, rogue Knight capability escalation, partition isolation, RPC anti-replay, revoked node quarantine) | 5 | `python3 -m pytest tests/test_distributed_chaos_scenarios.py` |
| `tests/unit/test_cluster_leasing_routing.py` | Task lease issuance, fencing sequence increments, lease expiration, capability router node selection, data locality policies | 2 | `python3 -m pytest tests/unit/test_cluster_leasing_routing.py` |
| `tests/unit/test_cluster_partition_revocation.py` | Network partition detection, fail-closed isolation, clock skew checks, revocation broadcast, reconnection verification | 2 | `python3 -m pytest tests/unit/test_cluster_partition_revocation.py` |
| Full Backend Pytest Suite | Comprehensive backend test coverage | 107 | `python3 -m pytest` |
| Frontend Vite Build | React Command Center production compilation | 108 modules | `npm --prefix frontend run build` |
