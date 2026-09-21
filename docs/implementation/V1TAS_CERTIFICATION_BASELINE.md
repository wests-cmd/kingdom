# Kingdom v1TAS (v1.0.0) — Certification Baseline & Subsystem Audit

**Release Codename:** `v1TAS`
**Canonical Version:** `1.0.0`
**Git Tag:** `v1.0.0`
**Status:** `VERIFIED PRODUCTION RELEASE`

---

## Subsystem Certification Matrix

| Subsystem | Classification | Evidence & Source Location |
|---|---|---|
| 1. Runtime | `VERIFIED` | Port fallback, health endpoints (`/health/live`, `/health/ready`), `desktop/launcher.js`, `tests/test_runtime_core.py` |
| 2. Task Engine | `VERIFIED` | State machine persistence (`tasks` table), monotonic leasing (`leases`), `backend/runtime/tasks.py` |
| 3. Scheduler | `VERIFIED` | Capability-based workload routing, data-locality matching, `backend/cluster/capability_router.py` |
| 4. Knight Execution | `VERIFIED` | Process-level E2E harness (`backend/cluster/knight_daemon.py`), `tests/e2e/test_process_distributed_execution.py` |
| 5. Node Registry | `VERIFIED` | Persisted SQLite hardware profiles & trust states (`knights` table), `backend/cluster/node_registry.py` |
| 6. Security Authority | `VERIFIED` | Server-side authorization, Ed25519 PoP signatures, Zero-Trust engine, `backend/security/zero_trust.py` |
| 7. Authorization | `VERIFIED` | Multi-dimensional scoped context & plan drift invalidation, `backend/security/scoped_authorization.py` |
| 8. Persistence | `VERIFIED` | SQLite WAL mode DB (`PRAGMA journal_mode=WAL`), repository pattern, `backend/storage/repository.py` |
| 9. Database Migrations | `VERIFIED` | Version-mapped deterministic schema migration engine, `backend/system/migrator.py` |
| 10. Update System | `VERIFIED` | 7-stage atomic update pipeline (`CHECK` -> `STAGE` -> `VERIFY` -> `BACKUP` -> `MIGRATE` -> `HEALTH`), `backend/system/updater.py` |
| 11. Rollback System | `VERIFIED` | Automatic health failure data & release version rollback, `backend/system/updater.py`, `scripts/rollback.sh` |
| 12. Desktop Application | `VERIFIED` | Standalone PyInstaller backend binary bundling (`desktop/bin/kingdom-backend`), `desktop/launcher.js` |
| 13. Docker Infrastructure | `VERIFIED` | Multi-stage Dockerfile (`node:24-alpine` -> `python:3.12-slim`) with isolated service topology in `docker-compose.yml` |
| 14. Frontend Application | `VERIFIED` | Production Vite static asset build (`frontend/dist`), `frontend/src/pages/` |
| 15. Versioning System | `VERIFIED` | Single authoritative source in `backend/state.py` (`1.0.0`), verified by `scripts/validate_version.py` |
| 16. CI System | `VERIFIED` | Automated testing & linting workflow `.github/workflows/ci.yml` |
| 17. Release Pipeline | `VERIFIED` | Automated release workflow `.github/workflows/release.yml` with SHA-256 and release-manifest.json generation |
| 18. Artifact Packaging | `VERIFIED` | Electron Builder packaging (`desktop/package.json`) producing Linux AppImage & DEB release artifacts |
| 19. Checksum Verification | `VERIFIED` | Cryptographic SHA-256 verification via `SHA256SUMS` and manifest audit |
| 20. Centipede Compatibility | `VERIFIED` | Protocol v1 metadata exposed via `/api/system/compatibility` and `release-manifest.json` |
| 21. Documentation | `VERIFIED` | Truthful installation, architecture, and maintenance guide in `README.md` and `docs/MAINTENANCE_MODE.md` |
| 22. Installation Lifecycle | `VERIFIED` | Clean machine first-run persistence contracts verified in `tests/test_installation_lifecycle.py` |
| 23. Failure Recovery | `VERIFIED` | Restart reconciliation and UNKNOWN state recovery in `tests/test_release_installation_contract.py` |
| 24. Chaos / Doomsday Testing | `VERIFIED` | 25-prompt injection gauntlet & multi-node clock skew endurance in `tests/chaos/doomsday/` |
