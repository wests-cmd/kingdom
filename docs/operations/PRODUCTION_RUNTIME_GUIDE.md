# Kingdom v40.2 Production Runtime & Operations Guide

## System Overview

Kingdom v40.2 is a zero-trust, failure-resilient distributed runtime infrastructure.

---

## 1. System Startup & Health Endpoints

### Local Python Backend Startup

```bash
python3 -m backend.main
```

### Health Readiness & Liveness Inspection

- **Liveness Endpoint:** `GET /health/live` (Returns HTTP 200 `{"status": "live"}`)
- **Readiness Endpoint:** `GET /health/ready` (Returns HTTP 200 `{"status": "ready"}` when database, scheduler, and security engines are initialized)
- **System Diagnostics:** `GET /system/check` and `GET /diagnostics/export`

---

## 2. Emergency Security Incident Mode

Operators can activate emergency lockdown to freeze all autonomous workflows, revoke active capabilities, and block external network actions:

```python
from backend.runtime.workflow_engine import EmergencyIncidentMode

incident_mode = EmergencyIncidentMode()
incident_mode.activate_emergency_lockdown(
    operator="admin",
    reason="Anomalous network spike / credential leak investigation"
)
```

To deactivate emergency lockdown:

```python
incident_mode.deactivate_emergency_lockdown(operator="admin")
```

---

## 3. Resilience Infrastructure

1. **Idempotency Manager:** Deduplicates duplicate tasks and retries via SHA-256 parameter hashes (`IdempotencyManager`).
2. **Circuit Breaker:** Automatically trips to `OPEN` state after 3 consecutive provider failures, cooling down for 30s before entering `HALF_OPEN` state (`CircuitBreakerEngine`).
3. **Dead-Letter Queue:** Automatically captures permanently failed tasks with retry metadata (`DeadLetterQueue`).
4. **Reconciliation Engine:** Resolves `UNKNOWN` external execution states into `VERIFIED_SUCCESS`, `VERIFIED_FAILURE`, or `REQUIRES_HUMAN_REVIEW` (`ReconciliationEngine`).
5. **Rate Limiting:** Enforces token bucket limits per client/actor (`RateLimiterEngine`).

---

## 4. Disaster Recovery & Backup Procedures

- **Database Persistence:** SQLite database stored at `data/kingdom.db`. Backup via atomic file copy or SQLite WAL checkpointing.
- **Cryptographic Identities:** Stored in `data/identities/`. Backup `kingdom_identity.json` securely.
- **Recovery Point Objective (RPO):** < 1 second (WAL mode persistence).
- **Recovery Time Objective (RTO):** < 5 seconds (FastAPI backend restart).
