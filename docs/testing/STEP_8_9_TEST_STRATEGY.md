# Step 8 & Step 9 Testing & Verification Strategy

## Executive Summary

Kingdom v40.2 enforces continuous automated testing across unit, integration, security adversarial, concurrency, chaos, and frontend build targets.

---

## Test Suite Inventory

| Test Module | Coverage Scope | Test Count | Execution Command |
|---|---|---|---|
| `tests/unit/test_intelligence_lifecycle.py` | E2E intelligence feedback, hypothesis gating, governance checks, skill rollback | 2 | `python3 -m pytest tests/unit/test_intelligence_lifecycle.py` |
| `tests/unit/test_extension_platform.py` | Extension manifests, trust registry, sandbox isolation, tool registry, event bus, updates & rollbacks | 6 | `python3 -m pytest tests/unit/test_extension_platform.py` |
| `tests/test_adversarial_extension_learning.py` | Prohibited permission rejection, tool permission escalation, event bus rate limiting, revoked extension blocks, poisoned learning detection | 5 | `python3 -m pytest tests/test_adversarial_extension_learning.py` |
| `tests/unit/test_distributed_infrastructure_and_learning_evolution.py` | Node disappearance task reassignment, conflict resolution, sandbox hypothesis gating | 3 | `python3 -m pytest tests/unit/test_distributed_infrastructure_and_learning_evolution.py` |
| `tests/test_security.py` | Capability check authorization, prompt injection firewall, audit logging | 14 | `python3 -m pytest tests/test_security.py` |
| `tests/test_runtime_core.py` | Task scheduling, polling completion, state management | 9 | `python3 -m pytest tests/test_runtime_core.py` |
| `tests/unit/test_cluster_federation.py` | Ed25519 pairing, signed RPC transport, heartbeat monitoring | 10 | `python3 -m pytest tests/unit/test_cluster_federation.py` |
| `tests/unit/test_mobile_knowledge_skills_governance.py` | Mobile challenge verification, multi-modal ingestion, financial execution | 4 | `python3 -m pytest tests/unit/test_mobile_knowledge_skills_governance.py` |
| `tests/unit/test_native_desktop_mobile_e2e.py` | Native application process supervision and health readiness polling | 1 | `python3 -m pytest tests/unit/test_native_desktop_mobile_e2e.py` |

---

## Execution Commands

- **Backend Pytest Suite:** `python3 -m pytest` (71/71 tests passing)
- **Frontend Production Build:** `npm --prefix frontend run build` (108 Vite modules compiled)
