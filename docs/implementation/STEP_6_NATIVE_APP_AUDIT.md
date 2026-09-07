# KINGDOM STEP 6 NATIVE DESKTOP APPLICATION AUDIT REPORT

## 1. RUNTIME VS DESKTOP SHELL BOUNDARY AUDIT
- **Kingdom Core Runtime (`backend/`)**: FastAPI server, SQLite database (`data/kingdom.db`), Zero-Trust capability firewall, Swarm orchestration, Memory stores, AI Maps, Skill engine, and Learning loop.
- **Desktop Application Shell (`desktop/`)**: Native application wrapper managing background process lifecycle (`start`, `stop`, `restart`), health polling (`/health/ready`), system doctor diagnostics, and native window rendering.
- **Kingdom Mobile (`apps/mobile/`)**: Bounded client interface communicating with the desktop/server runtime over authenticated, paired connections (`/mobile/*`).
- **Web Interface**: Optional developer and remote administration interface; no longer mandatory for ordinary desktop operation.

## 2. REFACTORING & PACKAGING PREREQUISITES
- Local process spawning: Managed via `desktop/launcher.js` with port binding and health check verification.
- IPC Security: Authenticated bridge preventing unauthorized web scripts from executing local shell commands.
- Configuration & DB: Desktop application and local runtime share identical `data/kingdom.db` and `configs/` state.
