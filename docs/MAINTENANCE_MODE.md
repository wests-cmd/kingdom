# Kingdom — Maintenance Mode & Operating Protocol

## 1. Operating Status
- **Status:** `PRODUCTION MAINTENANCE MODE`
- **Architecture Lock:** `ACTIVE`
- **Feature Freeze:** `ACTIVE`

Kingdom has completed all 20 operational core subsystems and is locked in production maintenance mode. Standard development consists of minor bug fixes, security patches, dependency updates, performance tuning, and documentation improvements.

---

## 2. Release Cadence
- **Standard Cadence:** Approximately every 1–2 months (30–60 day release window).
- **Out-of-Band Emergency Cadence:** Immediate release upon discovery of critical security vulnerabilities or severe data corruption defects.
- **Empty Cycle Policy:** If no material fixes or security updates occur during a 60-day cycle, no new release artifact is published.

---

## 3. Scope Classification

### Allowed Maintenance Changes
- Bug fixes and defect remediation.
- Zero-day security updates and dependency vulnerability patches.
- UI polish and accessibility enhancements.
- Performance and database query optimizations.
- Documentation updates and developer guidance updates.
- Packaging and CI/CD reliability updates.

### Prohibited Changes (Require Architectural Review)
- Redesigning stable subsystems (e.g. `RPCSecureTransport`, `NodeRegistry`, `TaskLeaseManager`).
- Introducing new external execution frameworks.
- Modifying zero-trust security authority boundaries or bypassing server-side authorization.
- Breaking API or schema compatibility without Centipede OS compatibility negotiation.

---

## 4. Release Checklist
1. **Version Synchronization:** Ensure `STATE["version"]` in `backend/state.py` matches all package manifests (`frontend/package.json`, `desktop/package.json`, `apps/mobile/package.json`).
2. **Version Validation:** Execute `python3 scripts/validate_version.py` to confirm zero version drift.
3. **Test Suite Verification:** Run `python3 -m pytest` across all unit, integration, security, process E2E, and doomsday chaos test suites.
4. **Build Verification:** Verify PyInstaller binary compilation (`desktop/bin/kingdom-backend`), frontend static build (`frontend/dist`), and Electron packaging (`desktop/dist`).
5. **Release Manifest & Checksum Generation:** Confirm `release-manifest.json` and `SHA256SUMS` cryptographically verify all published release staging artifacts.
