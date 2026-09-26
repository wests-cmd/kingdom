# Kingdom v1TAS (v1.0.0) — Release Certification & Maintenance Documentation

**Display Name:** Kingdom v1TAS
**Semantic Version:** 1.0.0
**Git Release Tag:** v1.0.0
**Release Channel:** stable
**Authoritative Version Source:** `backend/state.py` (`STATE["version"] = "1.0.0"`)

---

## 1. Release Architecture & Version Identity

Kingdom enforces single-source versioning. All sub-components derive their version string from `backend/state.py` or synchronized package manifests verified by `scripts/validate_version.py`.

- **Backend API:** `1.0.0` (Exposed via `GET /api/system/version` and `GET /status`)
- **Frontend UI:** `1.0.0` (`frontend/package.json`)
- **Desktop Application Shell:** `1.0.0` (`desktop/package.json`)
- **Mobile Gateway Client:** `1.0.0` (`apps/mobile/package.json`)
- **Docker Metadata:** `1.0.0` (`docker-compose.yml`)

---

## 2. Release Artifacts & Verification

The release automation pipeline (`.github/workflows/release.yml`) builds and publishes official release artifacts to GitHub Releases:

| Artifact Filename | Platform / Arch | Package Type | Checksum |
|---|---|---|---|
| `Kingdom-1.0.0.AppImage` | Linux x86_64 | Native Desktop AppImage | Verified in `SHA256SUMS` |
| `kingdom-desktop_1.0.0_amd64.deb` | Linux x86_64 | Debian Package | Verified in `SHA256SUMS` |
| `kingdom-backend-linux-x86_64` | Linux x86_64 | PyInstaller Standalone Binary | Verified in `SHA256SUMS` |
| `SHA256SUMS` | Multi-platform | Cryptographic Checksum File | Verified via `sha256sum -c` |
| `release-manifest.json` | Multi-platform | Machine-readable Release Manifest | Validated against semver |

---

## 3. Centipede OS Compatibility Protocol

Every release manifest (`release-manifest.json`) and runtime API endpoint (`/api/system/compatibility`) exposes Centipede OS compatibility metadata:

```json
{
  "product": "Kingdom",
  "version": "1.0.0",
  "release_name": "Kingdom v1TAS",
  "tag": "v1.0.0",
  "compatibility": {
    "kingdom_api_version": "v1",
    "centipede_protocol_version": "v1",
    "schema_version": "1.0"
  }
}
```

---

## 4. Maintenance & Upgrade Guidelines

### Normal Future Release Process
1. Commit code changes to `main` branch.
2. Ensure `backend/state.py` version increment follows Semantic Versioning (`PATCH` for bug fixes, `MINOR` for backward-compatible features, `MAJOR` for breaking changes).
3. Execute `python3 scripts/validate_version.py` to synchronize manifests.
4. Trigger `.github/workflows/release.yml` via git tag push (`vX.Y.Z`) or manual GitHub Actions workflow dispatch.

### Failure Recovery & Rollback
If a deployed update fails health check validation:
1. System Updater (`backend/system/updater.py`) automatically invokes 7-stage rollback.
2. Data backups stored in `data/backups/` are automatically restored.
3. Database schema migrations revert safely to compatible previous state.
