# 👑 KINGDOM v40.1 — Core Distributed Infrastructure & AI Runtime

Kingdom is a lightweight, high-performance distributed infrastructure and multi-agent execution runtime. It acts as the core substrate for autonomous swarms, node orchestrations, zero-trust security boundaries, persistent memory graphs, and skill maps.

Kingdom is designed to run standalone on local machines, edge devices (Raspberry Pi), server instances, or Docker containers, while also serving as the core runtime bundled by **Centipede OS**.

---

## 🏗 System Architecture

```
                                  KINGDOM RUNTIME
                                         │
       ┌─────────────────────────────────┼─────────────────────────────────┐
       │                                 │                                 │
COMMANDER ENGINE                 KNIGHT WORKERS                    SCOUT SENSORS
(Orchestration & State)      (Execution Nodes)                 (Passive Telemetry)
       │                                 │                                 │
       └─────────────────────────────────┼─────────────────────────────────┘
                                         │
                              ZERO-TRUST SECURITY
                   Capability Check | Persistent Approval Engine
                                         │
                           SQLITE DATA REPOSITORY
                 Tasks | Knights | Events | Memory | Skills
```

---

## ⚡ Current Status (v40.1 Technical Source of Truth)

| Subsystem | Status | Description |
| :--- | :--- | :--- |
| **Commander Orchestrator** | `WORKING` | Direct task dispatch, active swarm node monitoring, lifecycle state machine |
| **Knight Workers** | `WORKING` | Capabilities reporting, task execution pipeline, status heartbeats |
| **Scout Sensors** | `WORKING` | System telemetry collection, passive monitoring |
| **SQLite Persistence** | `WORKING` | Real SQLite repository (`data/kingdom.db`) for tasks, knights, memory, events, and skills |
| **Zero-Trust Security** | `WORKING` | Capability authorization (`permissions.py`), persistent human approvals (`approvals.json`), audit logging (`audit.jsonl`), prompt firewall |
| **AI Skill Map & Bundler**| `WORKING` | Skill dependency resolution engine, department scope selection, circular dependency detection, bundle builder |
| **Realtime WebSockets** | `WORKING` | Live event bus streaming, frontend WebSocket reconnection engine |
| **Setup Installer** | `WORKING` | One-command Python script (`scripts/kingdom_setup.py`) & POSIX installer (`scripts/install.sh`) |
| **Command Center UI** | `WORKING` | Vite/React dark graphite dashboard (`#0b0e14`), subtle blue accents, restrained security red |

---

## 🚀 Getting Started & Installation

### Option 1: One-Command Setup Script (POSIX / Python)
```bash
python3 scripts/kingdom_setup.py
```
Or non-interactive automated installation:
```bash
python3 scripts/kingdom_setup.py --non-interactive
```

### Option 2: Developer Installation
1. **Clone & Setup Environment:**
   ```bash
   git clone https://github.com/wests-cmd/kingdom.git
   cd kingdom
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start Backend Server:**
   ```bash
   python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

3. **Start Frontend Command Center:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 🛡 Zero-Trust Security & Governance

Kingdom enforces a deny-by-default capability model:
1. **Actor Verification:** Every operation requires an authenticated and verified actor context.
2. **Capability Check:** Execution commands (`process.execute`, `filesystem.write`, `network.outbound`) are validated against active permissions.
3. **Risk-Classified Approvals:** Operations tagged as `HIGH` risk trigger an explicit approval request held in `data/approvals.json` until approved via UI or REST API.
4. **Audit Trail:** All security events are masked for credentials (`[REDACTED]`) and recorded in `data/logs/audit.jsonl`.
5. **Prompt Firewall:** Direct AI prompts are inspected for injection attacks (`ignore rules`, `system override`, `bypass approval`).

---

## 🧩 AI Skill Map & Dependency Engine

Kingdom features a dependency-aware AI Skill Map:
- **Dependency Resolution:** Automatically maps required skills, departments, tools, and capabilities.
- **Circular Loop Defense:** Detects circular dependency chains (A &rarr; B &rarr; A) and halts execution safely.
- **Shared Dependency Retention:** Safe removal logic ensures that shared dependencies needed by remaining active skills are not accidentally uninstalled.
- **Bundler:** Group multiple skills into custom bundles with deduplicated department requirements.

---

## 🧪 Testing & Verification

Run the full Python test suite (including unit, integration, and adversarial security tests):
```bash
python3 -m pytest
```

Build the production frontend bundle:
```bash
npm --prefix frontend run build
```

---

## 📄 License
MIT License.
