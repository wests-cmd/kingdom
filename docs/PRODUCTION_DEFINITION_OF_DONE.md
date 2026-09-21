# Kingdom — Production Definition of Done (DoD)

This document establishes the explicit checklist and verification requirements for Kingdom to be certified as `PRODUCTION READY`.

---

## 1. Core Architecture & Zero-Trust Security Checklist

- [x] **Single Version Authority:** Single source of version truth in `backend/state.py`, verified deterministically by `scripts/validate_version.py`.
- [x] **Standalone Desktop Runtime:** Executable binary compiled via PyInstaller (`desktop/bin/kingdom-backend`) bundled into Electron packaging (`desktop/package.json` `extraResources`) requiring zero user Python runtime installation.
- [x] **Durable Task Lifecycle:** SQLite persistence for tasks (`tasks` table) and leases (`leases` table) enforcing valid state machine transitions (`CREATED` -> `LEASED` -> `RUNNING` -> `SUCCEEDED`/`FAILED`).
- [x] **Monotonic Fencing Tokens:** Monotonic fence sequence validation in `TaskLeaseManager` rejecting stale result submissions from superseded worker nodes.
- [x] **Ed25519 Signed RPC & Replay Protection:** Authenticated RPC network endpoint (`/nodes/rpc`) enforcing message signature verification and SQLite `rpc_replay` table deduplication.
- [x] **Zero-Trust Node Security:** Multi-node Knight enrollment with single-use pairing codes, Ed25519 proof-of-possession signatures, and node state enforcement (`REVOKED`, `QUARANTINED`, `REJECTED`).
- [x] **Strict Data Truth:** Environment option `STRICT_TRUTH_MODE=true` reporting `null` for unprobeable metrics instead of synthetic defaults, with demo skill fixtures separated into `scripts/bootstrap_demo.py`.
- [x] **Atomic Updater & Health Rollback:** 7-stage atomic update pipeline (`CHECK` -> `STAGE` -> `VERIFY` -> `BACKUP` -> `MIGRATE` -> `HEALTH CHECK` -> `SUCCESS`/`AUTOMATIC ROLLBACK`).
- [x] **Production Docker Topology:** Multi-stage Dockerfile (`node:24-alpine` -> `python:3.12-slim`) running pre-built static assets on production server without Vite dev server dependencies.

---

## 2. Verification Matrix

| Subsystem | Requirement | Status | Verification Source |
|---|---|---|---|
| Core Runtime | Port fallback & health checks | `PASS` | `tests/test_deployment_master_smoke_suite.py` |
| Distributed Execution | Real OS process Commander + 2 Knights | `PASS` | `tests/e2e/test_process_distributed_execution.py` |
| Doomsday / Chaos | RPC clock skew & endurance | `PASS` | `tests/chaos/doomsday/test_distributed_doomsday_endurance.py` |
| Security & CORS | Restricted origin enforcement | `PASS` | `tests/test_security.py` |
| Versioning | Deterministic validation script | `PASS` | `scripts/validate_version.py` |
| Release Automation | Automated release pipeline | `PASS` | `.github/workflows/release.yml` |
