# STEP 16 — DISTRIBUTED RUNTIME & PROCESS-TO-PROCESS EXECUTION ARCHITECTURE

## OVERVIEW

Kingdom Step 16 implements multi-process distributed runtime infrastructure, separating the **Commander** control plane from distributed **Knight** worker daemons. Communication between nodes occurs over operating system network sockets (HTTP / WebSocket) using Ed25519 proof-of-possession signatures and zero-trust capability-based authorization.

---

## NETWORK ARCHITECTURE & PORT MAPPINGS

```text
                               COMMANDER PROCESS (FastAPI / Uvicorn)
                                   Listen Port: 8000 / 8090
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             │                                                           │
             ▼                                                           ▼
     KNIGHT DAEMON A                                            KNIGHT DAEMON B
    (Coder Worker Node)                                      (Researcher Worker Node)
   Listen Port: 8001 / 8091                                   Listen Port: 8002 / 8092
Capabilities: [coder.execute, gpu]                        Capabilities: [researcher.execute]
```

---

## DISTRIBUTED PROCESS LIFECYCLE

1. **Daemon Initialization (`backend/cluster/knight_daemon.py`):**
   - Knight loads or generates persistent Ed25519 identity keypair (`KnightIdentity`).
   - Daemon state initializes to `DISCOVERED`.

2. **Single-Use Pairing Request:**
   - Knight issues HTTP POST request to `/nodes/pair` with pairing code and signed payload (`f"{pairing_code}:{knight_id}:{kingdom_id}"`).
   - Node registry records Knight in `PENDING_APPROVAL` (WAITING_FOR_APPROVAL) state. Unapproved nodes cannot receive privileged work.

3. **Commander Human Approval:**
   - Commander approves Knight via POST `/nodes/{node_id}/approve` with explicit `granted_capabilities`.
   - Node transitions to `APPROVED` / `CONNECTED`.

4. **Network Capability Synchronization & Routing:**
   - Knight advertises granted capabilities to Commander.
   - Commander router (`CapabilityRouter`) matches task capability requirements against connected physical Knight processes.

5. **Process-Level Task Execution:**
   - Commander submits task to assigned Knight daemon over network socket.
   - Knight executes task and returns signed execution result.

6. **Process Disconnect, Reconnect & Revocation:**
   - Process termination triggers heartbeat timeout and updates status to `DISCONNECTED`.
   - Process restart restores persistent identity and automatically re-authenticates.
   - Node revocation via POST `/nodes/{node_id}/revoke` invalidates permissions and refuses reconnection attempts.

---

## VERIFICATION EVIDENCE

- **Process-Level E2E Test Suite:** `tests/e2e/test_process_distributed_execution.py`
- **Docker Production Compose Topology:** `docker-compose.production.yml`
- **CI Workflow Integration:** `.github/workflows/ci.yml`
