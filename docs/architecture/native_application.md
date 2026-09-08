# KINGDOM ARCHITECTURE: NATIVE DESKTOP APPLICATION & RUNTIME SUPERVISOR

Kingdom Desktop (`desktop/main.js`, `launcher.js`, `doctor.js`) operates as a self-contained native application wrapper managing local Kingdom Core backend process startup, readiness polling (`/health/ready`), and IPC window rendering.

## Architectural Boundaries
```
                  KINGDOM CORE RUNTIME
               (FastAPI, SQLite, Swarm)
                           │
             ┌─────────────┴─────────────┐
             │                           │
      Kingdom Desktop              Kingdom Mobile
    (IPC Shell / Launcher)      (Companion Gateway)
```

## Desktop Runtime Supervision
- Startup: `launcher.js` spawns local `python3 -m uvicorn backend.main:app --port 8000` process.
- Readiness Polling: `launcher.js` polls `/health/ready` until SQLite connection, Zero-Trust engine, and NodeRegistry confirm readiness.
- Desktop Shell: `desktop/main.js` opens native window targeting `http://localhost:8000`.
- Process Shutdown: On application window close, `main.js` sends `SIGTERM` to local backend process.
