# STEP 6 ARCHITECTURE: NATIVE DESKTOP APPLICATION & RUNTIME SHELL

Kingdom Desktop provides a native application shell (`desktop/main.js` and `launcher.js`) that directly manages local Kingdom backend process startup, health polling (`/health/ready`), and window loading without requiring a standalone browser or manual terminal commands.

## Process Lifecycle Model
1. User double-clicks Kingdom Desktop.
2. `desktop/main.js` launches local FastAPI backend via `desktop/launcher.js`.
3. Launcher polls `/health/ready` until SQLite DB, Zero-Trust security engine, and NodeRegistry confirm readiness.
4. Native window opens and displays the Kingdom Command Center interface.
5. On window close, `main.js` triggers graceful backend process shutdown.
