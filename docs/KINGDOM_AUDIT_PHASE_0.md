# KINGDOM AUDIT — PHASE 0
**Ecosystem Architecture & Kingdom Repository Audit**
*Target Repository: wests-cmd/kingdom*
*Target Version: v40.1*

---

## 1. Current State
The `wests-cmd/kingdom` repository is designed as a distributed AI runtime and swarm orchestration platform. In its current version (v40.1), the codebase presents a complete architectural skeleton with FastAPI serving as the web application layer, a React/Vite web interface in `frontend/`, and multiple specialized Python packages under `backend/`.

### Inventory Summary
- **Directories**: `backend/`, `frontend/`, `configs/`, `data/`, `scripts/`, `migrations/`.
- **Entry Points**: `backend/main.py` (FastAPI backend), `frontend/src/main.jsx` (Vite frontend).
- **APIs**: REST endpoints (`/status`, `/start`, `/stop`, `/mode`) and WebSocket endpoint (`/ws`).
- **Configuration**: YAML config files in `configs/` (`default.yaml`, `control_levels.yaml`, `runtime.yaml`, `update.yaml`).
- **Containerization**: `Dockerfile` (Python 3.11 backend) and `docker-compose.yml` (backend + frontend).
- **Documentation**: `README.md`, `LICENSE`, `COMMERCIAL_USE.md`.
- **Testing**: No test files existed in `tests/` prior to Phase 0 audit baseline.

---

## 2. What Actually Works
1. **HTTP Server & Entry Points**: FastAPI launches reliably via `uvicorn backend.main:app` and `scripts/start.sh`.
2. **Runtime State Control**: REST endpoints `/status`, `/start`, `/stop`, and `/mode` successfully read and mutate global state in `backend/state.py`.
3. **WebSocket Heartbeat**: `/ws` accepts incoming WebSocket connections and streams a JSON heartbeat payload every second.
4. **Frontend UI Scaffold**: Vite dev server compiles and serves React components with styling and ForceGraph visual placeholders.
5. **Configuration Parsing**: YAML configuration files in `configs/` are standard and parseable with `pyyaml`.

---

## 3. What Does Not Work (Stubs, Mocks, and Gaps)
While the directory structure contains comprehensive module coverage, most backend logic currently consists of lightweight stubs and mock returns:
1. **Swarm Execution**: `SwarmEngine.process()` assigns tasks to hardcoded knight names and returns mock scoring without invoking knight execution logic.
2. **Knights Execution**: Knight implementations (`CoderKnight`, `PlannerKnight`, etc.) return static completion dictionaries (`{"status": "completed"}`) without tool access or LLM invocation.
3. **Cluster & Discovery**: `NodeRegistry` maintains an in-memory list `NODES = []`. `Heartbeat`, `AutoConnector`, `TopologySync`, and `RejoinManager` return static success dicts without network calls or peer discovery.
4. **Security & Zero Trust**: `ZeroTrust.validate()` unconditionally returns `True`. `InjectionDetector` relies on 3 hardcoded string patterns. No token verification, API authentication, or TLS exists.
5. **Memory System**: `VectorStore` keeps raw python objects in a list without vector math or embedding models. `GraphMemory` and `SnapshotManager` write simple JSON structures without graph indexing or search capability.
6. **Integrations**: Integrations (`Ollama`, `Discord`, `IPFS`, `Tailscale`) contain empty client classes and mock response methods without real driver connections.

---

## 4. Architecture Diagram

### Current System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Kingdom UI (React / Vite)                │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / WS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Backend (backend/main.py)           │
├──────────────────────────────┬──────────────────────────────┤
│ REST Endpoints (/status, etc)│ WebSocket Stream (/ws)       │
└──────────────┬───────────────┴──────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐┌─────────────────────────────┐
│   Global STATE dict          ││  Heartbeat Generator        │
└──────────────┬───────────────┘└─────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│              Backend Subsystem Stubs (In-Memory)            │
│  ├── Swarm Engine & Knights (Mock execution)                │
│  ├── Cluster & Node Registry (In-memory list)               │
│  ├── Security Firewall & ZeroTrust (Mock check)             │
│  ├── Memory & Vector Index (JSON / List stub)               │
│  └── Integrations (Ollama, IPFS, Tailscale stubs)          │
└─────────────────────────────────────────────────────────────┘
```

### Future Centipede Ecosystem Architecture
```
                         CENTIPEDE ECOSYSTEM
                                  │
                         ┌────────┴────────┐
                         │                 │
                    CENTIPEDE OS        KINGDOM
                  User Environment    Core Runtime
                         │                 │
                  Centipede AI        Commander
                         │              Knights
                  Centipede Harness     Scouts
                         │              Security
                         │              Swarm
                         │              Routing
                         │              Memory
                         │              Events
                         │
                  Docker / VM / USB
                  / Live USB / Native
```

---

## 5. Commander Status
- **Current Location**: Implicitly embedded inside `backend/main.py` and `RuntimeEngine` (`backend/runtime/engine.py`).
- **State Management**: Uses in-memory dictionary `STATE` in `backend/state.py`. State is lost upon server restart.
- **Node Communication**: No network-based node communication protocol implemented.
- **Authentication/Authorization**: None present.
- **Multi-node Orchestration**: Lacks distributed task routing across remote processes or instances.

---

## 6. Knight Status
- **Implementation**: Knights exist as stub classes under `backend/knights/` deriving from `BaseKnight`.
- **Specializations**: Defined as static string mapping in `backend/swarm/specialization.py`.
- **Capabilities**: No real capability reporting, resource inspection, or sandboxed execution environment.
- **Execution**: `execute(task)` returns `{ "knight": self.name, "task": task, "status": "completed" }` synchronously without side effects.

---

## 7. Scout Status
- **Current Existence**: **Does not exist** in the current codebase.
- **Requirements for Scout Nodes**:
  1. Lightweight daemon designed for resource-constrained edge devices (Raspberry Pi, IoT, lightweight VMs).
  2. System telemetry collector (CPU, RAM, Disk, Temperature, Network I/O).
  3. Local discovery probe and lightweight ping health checker.
  4. Minimal footprint (no heavy ML/LLM library dependencies).

---

## 8. Security Status
- **Authentication & Authorization**: Currently missing across HTTP and WebSocket endpoints.
- **Prompt Firewall**: Performs string inclusion check against three hardcoded phrases (`"ignore previous instructions"`, `"send passwords"`, `"system override"`).
- **Zero Trust Engine**: Always validates actors positively (`{"validated": True}`).
- **Audit Logging**: Uses standard logging to stdout; lacks tamper-evident or persistent audit trails.
- **Execution Safety**: No container isolation or restricted process boundaries for tool execution.

---

## 9. Docker Status
- **Current Container Setup**:
  - `Dockerfile`: Single Python 3.11 container serving `uvicorn backend.main:app`.
  - `docker-compose.yml`: Launches `kingdom-backend` and `kingdom-ui` (Node 20 running `npm run dev`).
- **Gaps**: Does not distinguish container profiles for `centipede/commander`, `centipede/knight`, `centipede/scout`, or `centipede/security`. Dynamic container spawning is not supported.

---

## 10. API Inventory

### Implemented REST & WS Endpoints
| Endpoint | Method | Input | Output | Auth | Purpose | Status |
|---|---|---|---|---|---|---|
| `/status` | GET | None | `{"running": bool, "mode": str, "version": str}` | None | Returns runtime state | Functional |
| `/start` | POST | None | `{"status": "started"}` | None | Sets `running` to `True` | Functional |
| `/stop` | POST | None | `{"status": "stopped"}` | None | Sets `running` to `False` | Functional |
| `/mode` | GET | None | `"adaptive"` (str) | None | Returns active mode | Functional |
| `/ws` | WS | None | `{ "type": "heartbeat", "status": "alive" }` | None | Real-time state streaming | Functional |

### Required Future Endpoints
- `POST /api/v1/nodes/register`: Register new Knight/Scout nodes with public key and capabilities.
- `POST /api/v1/nodes/heartbeat`: Periodic heartbeat check with telemetry data.
- `GET /api/v1/nodes`: List active cluster nodes and health status.
- `POST /api/v1/tasks/submit`: Submit execution task payload with permission requirements.
- `GET /api/v1/tasks/{task_id}`: Query task status and execution logs.
- `POST /api/v1/tasks/{task_id}/cancel`: Cancel active task execution.
- `GET /api/v1/security/audit`: Retrieve security audit trail logs.
- `GET /api/v1/events/stream`: Server-Sent Events (SSE) or WS stream for cluster events.

---

## 11. Cross-Platform Status
- **Current Runtime**: Pure Python backend and JavaScript frontend; runs on Linux, macOS, and Windows.
- **Shell Scripts**: Existing helper scripts (`scripts/start.sh`, `scripts/install.sh`) assume POSIX shell environments.
- **Platform Abstraction Needed**: Native process execution, hardware telemetry, and container management must be wrapped behind abstract interfaces (e.g., `OSProvider` / `PlatformDriver`) to cleanly support Windows, Debian/Ubuntu, Kali, Fedora, macOS, and Raspberry Pi OS (ARM64).

---

## 12. Kingdom / Centipede Architectural Boundary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CENTIPEDE OS                               │
│  - User Interface & Desktop Environment (GUI, Shell, Settings)         │
│  - Universal Search, Installer, Software/Package Management             │
│  - Personal Context, User Policy Configuration & Permission Controls    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ User Intent & Approvals
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              CENTIPEDE AI                               │
│  - Intent Parser & Task Planner (JARVIS-style interaction)              │
│  - Explanation Generator & Multi-modal Voice/Text Interface             │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Validated Plan Specification
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            CENTIPEDE HARNESS                            │
│  - Permission Verification Engine & Human-in-the-Loop Gateway           │
│  - Policy Enforcement & Sandboxed Tool Execution Router                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Authorized Execution Payload
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                 KINGDOM                                 │
│  - Distributed Node Clustering (Commander, Knight, Scout)               │
│  - Swarm Orchestration, Task Queueing, and Routing                      │
│  - Network Event Bus, Node State Synchronization & Heartbeats           │
│  - Graph Memory, Zero-Trust Validation & System Telemetry               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Critical Problems
1. **Lack of Authenticated Node Communication**: Any process capable of reaching the HTTP/WS ports can alter runtime state without credentials.
2. **In-Memory Volatile State**: Node registry, tasks, and runtime states are wiped on process restart.
3. **Absence of Tool Execution Sandboxing**: Knights currently execute directly in process space without isolation.
4. **Mock Security Layers**: Prompt firewall and injection detection provide zero protection against real adversarial inputs.

---

## 14. Recommended Changes
1. **Node Identity & Security**: Implement mTLS or cryptographic token-based node registration for Commander-Knight communications.
2. **Abstract Node Service Architecture**: Refactor `backend/` to separate entry points for `Commander`, `Knight`, and `Scout` nodes.
3. **Real Storage Engine**: Replace raw JSON persistence with SQLite/SQLAlchemy for task state and node metadata persistence.
4. **Scout Module Implementation**: Create a lightweight system monitoring module (`backend/scout/`) for lightweight nodes.

---

## 15. Prioritized Roadmap

### P0 — Critical Baseline (Required before reliable runtime)
- Add comprehensive API endpoint unit testing.
- Implement structured error handling and persistent SQLite storage for runtime state and node registry.
- Establish mTLS / HMAC token authentication for Commander APIs.

### P1 — Core Distributed Clustering
- Implement real node registration and RPC/HTTP ping protocol between Commander and Knights.
- Build real capability discovery (CPU, RAM, GPU, OS) in Knights.
- Implement task dispatch, cancellation, and execution status callbacks.

### P2 — Containerization & Isolation
- Create multi-stage Docker builds for `centipede/commander`, `centipede/knight`, and `centipede/scout`.
- Implement Docker engine integration allowing Kingdom to spawn sandboxed tool containers safely.

### P3 — Cross-Platform Support
- Create platform abstraction adapters for Windows (Win32/PowerShell), Linux (systemd), and macOS.
- Ensure ARM64 / Raspberry Pi compatibility for Scout nodes.

### P4 — Centipede OS Integration
- Expose stable REST/WS OpenAPI specifications for Centipede OS UI consumption.
- Implement structured event streaming (SSE/WS) for Centipede OS notifications.

### P5 — Advanced Intelligence & Proactive Swarm
- Integrate graph memory and vector store indexing with local LLM backends (e.g. Ollama driver).
- Support proactive telemetry triggers and structured autonomous approval levels (Level 0 - Level 4).

---

## 16. Testing Strategy
1. **Unit Testing**: FastAPI `TestClient` tests for all HTTP and WebSocket endpoints.
2. **Cluster Integration Testing**: Simulated multi-node cluster tests using Docker Compose to verify node registration and heartbeats.
3. **Security Testing**: Verification of prompt injection filtering and permission boundary rejections.
4. **Cross-Platform Verification**: CI matrix testing on Ubuntu, Windows Server, and macOS runners.

---

## 17. Risks
1. **Breaking Owner Changes**: Modifications to core backend files could conflict with ongoing Kingdom development by the repository owner.
2. **Over-Coupling**: Tight coupling between Centipede OS UI code and Kingdom backend internals could hamper independent usability.
3. **Security Vulnerabilities**: Untrusted remote execution could expose host operating systems if tool execution is not strictly sandboxed.

---

## 18. Centipede OS Integration Plan
1. **Standalone Package Dependency**: Centipede OS will import/bundle Kingdom as a service daemon via standard APIs without modifying Kingdom source.
2. **Version Compatibility Contract**: Centipede OS versioning will strictly pin Kingdom API compatibility (e.g., `Centipede OS 0.1` requires `Kingdom >= 40.1 < 41.0`).
3. **IPC / HTTP Interface**: Centipede OS GUI will connect over local loopback (`http://127.0.0.1:8000`) or authenticated Unix domain socket.

---

## WHAT YOU CHANGED
1. Created `docs/KINGDOM_AUDIT_PHASE_0.md` containing the exhaustive Phase 0 engineering audit and architecture report.

---

## WHAT YOU RECOMMEND DOING NEXT
1. **Review Audit Findings**: The repository owner / architect should review the audit findings and confirm the proposed Kingdom/Centipede boundaries.
2. **Begin Phase 1 Tasks**: Once approved, create `tests/test_api.py` and implement P0 baseline authentication, SQLite persistence, and real node registration APIs.
