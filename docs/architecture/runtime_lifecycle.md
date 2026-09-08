# KINGDOM ARCHITECTURE: RUNTIME LIFECYCLE & PROCESS SUPERVISION

Kingdom Core runtime states and process supervision rules:

## Runtime States
- `STARTING`: Launcher spawning backend process and verifying database initialization.
- `RUNNING`: Backend process active and `/health/ready` returns HTTP 200 OK.
- `DEGRADED`: Backend active but database or node registry reporting health timeout.
- `STOPPING`: Shutdown signal sent (`SIGTERM`).
- `STOPPED`: Backend process terminated cleanly.
- `FAILED`: Backend process exited with error code or timed out during startup polling.
- `RECOVERING`: Supervisor attempting bounded process restart.
