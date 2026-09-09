# Step 12 — Identity Fabric & Scoped Authorization Architecture

## Overview

Kingdom v40.2 separates the intelligence layer from runtime execution authority. Identity is cryptographic and typed; authorization evaluates multi-dimensional contextual attributes (`WHO`, `WHAT`, `RESOURCE`, `CONDITIONS`, `DATA SCOPE`, `RISK`).

```text
CALLER / ACTOR (SystemIdentity)
 ↓
IDENTITY FABRIC (IdentityFabric Verification & State Check)
 [ AUTHENTICATED -> AUTHORIZED -> ACTIVE -> SUSPENDED -> QUARANTINED -> REVOKED ]
 ↓
PLAN DRIFT ENGINE (PlanDriftEngine Parameter Binding & Hash Check)
 ↓
SCOPED AUTHORIZATION ENGINE (ScopedAuthorizationEngine Risk & Scope Decision)
 ↓
INDEPENDENT VERIFICATION ENGINE (IndependentVerificationEngine State Check & UNKNOWN Output)
```

---

## Identity Lifecycle States

Identity states in `IdentityFabric` (`backend/security/identity_fabric.py`):
- `DISCOVERED`: Unauthenticated entity.
- `AUTHENTICATED`: Key/credential verified.
- `AUTHORIZED`: Capabilities mapped.
- `ACTIVE`: Active execution state.
- `SUSPENDED`: Temporarily suspended due to token expiration or security flag.
- `QUARANTINED`: Isolated due to suspicious behavior.
- `REVOKED`: Permanently revoked; execution blocked.

---

## Plan Drift Engine

When a plan is approved by a human or Commander, `PlanDriftEngine` (`backend/security/plan_drift.py`) creates an immutable parameter hash binding.
If an attacker or model attempts to modify parameters, substitute tools, or change target resources post-approval, `validate_plan_execution()` detects parameter drift and immediately invalidates authorization.

---

## Independent Verification & UNKNOWN State

`IndependentVerificationEngine` (`backend/security/verification_engine.py`) independently verifies filesystem, database, or API outcomes. If an external action cannot be independently confirmed, the state evaluates to `UNKNOWN` rather than collapsing into `SUCCESS`.
