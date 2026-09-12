# Kingdom v40.2.0 — Release Engineering Baseline

- **Authoritative Version:** `40.2.0` (`backend/state.py`)
- **Current Commit SHA:** `7137d68`
- **Test Metrics:** 161 passed / 0 failed / 0 skipped
- **CI Workflows:** `.github/workflows/ci.yml` (jobs: `test-backend`, `build-frontend`, `build-desktop-release`)
- **Desktop Targets:** Windows (`.exe` NSIS), macOS (`.dmg`), Linux (`.AppImage`, `.deb`)
- **Docker Targets:** Production single-container & multi-container compose
- **Update Engine:** `UpdaterEngine` (`backend/system/updater.py`) with SHA-256 validation & automatic rollback
- **Migration Engine:** `MIGRATION_REGISTRY` (`backend/system/migrator.py`)
- **Release Status:** `RELEASE CANDIDATE`
