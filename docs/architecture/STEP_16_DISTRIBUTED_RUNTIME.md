# Step 16 — Distributed Runtime Architecture

## Overview

Kingdom's distributed runtime coordinates multi-node task allocation using capability-based routing, task leasing, and fencing token validation.

---

## Task Leasing & Fencing Engine

`TaskLeaseManager` (`backend/cluster/task_leasing.py`) issues time-bounded leases (`TaskLease`) for assigned tasks:
- **Fencing Token Sequence:** Each lease assignment increments a monotonic fencing sequence number (`fencing_token`).
- **Duplicate Execution Prevention:** Stale workers attempting task completion with outdated fencing tokens receive `PermissionError`.
- **Lease Expiration:** Expired leases automatically invalidate execution authority.

---

## Capability-Based Router

`CapabilityRouter` (`backend/cluster/capability_router.py`) selects the optimal worker node based on:
1. **Node State:** Must be in `CONNECTED` or `APPROVED` state.
2. **Health Status:** Must report `healthy`.
3. **Capability Match:** Must possess the required capability in `granted_capabilities`.
4. **Data Locality Policy:** Enforces `local_only`, `transferable`, or `encrypted_transfer` rules.
5. **Hardware Profile:** Filters by minimum CPU cores (`cpu_cores`) and VRAM (`vram_mb`).
