# KINGDOM ARCHITECTURAL DECISION REVIEW (STEPS 7 & 8)

## 1. PRIMARY ROADMAP QUESTION
**Question:** What does Kingdom need to become a reliable, fault-tolerant distributed AI operating platform rather than a collection of features?
**Answer:** Kingdom requires a resilient, multi-node cluster state engine with deterministic reconciliation, automatic task workload reassignment upon unannounced node failures, and multi-metric sandbox experiment gating that prevents regressed intelligence skills or poisoned data from reaching active production execution.

## 2. DEPENDENCY & BOTTLENECK ANALYSIS
- **Primary Bottleneck:** Single point of failure or unannounced disconnection of remote Knight nodes executing assigned tasks.
- **Dependency Sequence:**
  1. Distributed Node Registration & Heartbeat Timeout Detection (`backend/cluster/`).
  2. Idempotent Task Re-queuing & Reassignment (`backend/runtime/tasks.py` & `backend/api.py`).
  3. Deterministic State Sync & Conflict Resolution (`backend/cluster/sync_engine.py`).
  4. Hypothesis Generation & Multi-Metric Sandbox Scoring (`backend/learning/`).
  5. Reversible Knight Specialization Evolution (`backend/knights/adaptive_knight.py`).

## 3. THREE-PASS DESIGN AUDIT MATRIX

| Pass | Focus | Mitigation Strategy |
|---|---|---|
| **Pass A (Happy Path)** | Single/Multi-device pairing, skill activation, task execution | Explicit state transitions and signed Ed25519 transport |
| **Pass B (Failure Path)** | Node crash, network timeout, duplicate requests | Idempotency headers (`X-Request-ID`), heartbeat expiry, task re-queuing |
| **Pass C (Adversarial Path)** | Key tampering, poisoning floods, cross-Kingdom leaks | Auto-quarantine, target Kingdom ID binding, prompt firewall |
