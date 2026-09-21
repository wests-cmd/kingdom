# Changelog

All notable changes to Kingdom will be documented in this file.

The format is based on [Keep a Changelog](https.keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — Kingdom v1TAS - 2026-09-21

### Highlights
- **First Stable Production Release:** `Kingdom v1TAS` (Semantic Version `1.0.0`, Git tag `v1.0.0`).
- **Zero-Trust Distributed AI Runtime:** Complete implementation and verification of all 20 core subsystems across authority, execution, networking, and resilience.

### Added
- **Single Source Versioning:** Created `scripts/validate_version.py` enforcing version consistency across backend (`1.0.0`), frontend, desktop, mobile, Git tags (`v1.0.0`), build artifacts, and release manifests.
- **Standalone Desktop Bundling:** Compiled PyInstaller standalone binary `desktop/bin/kingdom-backend` packaged into Electron resources, removing machine Python runtime dependencies for end-users.
- **Automated Production Release Pipeline:** Created `.github/workflows/release.yml` automating version validation, full pytest execution, PyInstaller binary compilation, frontend static build, Electron packaging, SHA-256 checksum generation, release-manifest creation, and GitHub release publishing.
- **Centipede OS Compatibility:** Added Centipede Protocol v1 compatibility metadata to `/api/system/compatibility` and `release-manifest.json`.

### Changed
- **Production Docker Multi-Stage Build:** Updated `Dockerfile` to multi-stage (`node:24-alpine` -> `python:3.12-slim`) running pre-built static assets on production server without Vite development server dependencies.
- **Maintenance Mode Protocol:** Locked architecture and established feature freeze in `docs/MAINTENANCE_MODE.md` and `docs/PRODUCTION_DEFINITION_OF_DONE.md`.
