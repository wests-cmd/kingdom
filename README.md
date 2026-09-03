# KINGDOM v40.2 — Distributed AI Runtime & Orchestration Infrastructure

[![Backend CI](https://github.com/wests-cmd/kingdom/actions/workflows/ci.yml/badge.svg)](https://github.com/wests-cmd/kingdom/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](requirements.txt)
[![Node Version](https://img.shields.io/badge/node-20%20%7C%2024-green)](frontend/package.json)

Kingdom (`wests-cmd/kingdom`) is the core distributed runtime and infrastructure layer for the Centipede ecosystem. It provides distributed task execution, swarm orchestration, zero-trust capability security, persistent memory, typed AI skill intelligence, continuous learning, and live operational APIs.

> **Architectural Separation:** Sledge sits above Kingdom as the user-facing agent layer. Kingdom operates strictly as the underlying runtime infrastructure, providing security boundaries, execution sandboxing, and node coordination.

---

## 1. IMPLEMENTATION STATUS

| Feature / Subsystem | Status | Description |
|---|---|---|
| **FastAPI Core Runtime** | ✅ Implemented | Live REST endpoints (`/status`, `/tasks`, `/security`, `/skills`, `/learning`) & `/ws` WebSocket stream |
| **Command Center UI** | ✅ Implemented | React/Vite web interface (`frontend/`) with dark graphite theme, live topology, Skills, & Learning pages |
| **Zero-Trust Security Engine** | ✅ Implemented | Capability-based authorizations, prompt firewall, risk classification, & human approval workflows |
| **AI Skill Intelligence** | ✅ Implemented | Typed/versioned `Skill` models, trust levels, lifecycle states (`SAVED`, `INSTALLED`, `ACTIVE`, `DISABLED`), & readiness reporting |
| **Skill Dependency Engine** | ✅ Implemented | Deterministic dependency resolution, constraint matching, circular dependency detection, & lock file manifests |
| **Skill Bundles & Map** | ✅ Implemented | Bundle validation, dependency deduplication, and structured intelligence graph mapping |
| **Kingdom Learning Engine** | ✅ Implemented | Outcome evidence collection, pattern evaluator, proposal generator, offline sandbox experiments, & auto-rollback |
| **Learning Poisoning Defense** | ✅ Implemented | Provenance verification, sample thresholds, and duplicate flood anomaly detection |
| **Agent Integration Boundary** | ✅ Implemented | Model Context Protocol (MCP) server interface (`backend/integrations/mcp_server.py`) & Python SDK (`sdk/kingdom_sdk.py`) |
| **Swarm & Routing Learning** | ✅ Implemented | `HybridRouter` incorporates historical learning evidence safely within policy constraints |
| **Installer** | ✅ Implemented | Hardened `scripts/install.sh` supporting Linux, macOS, Windows/WSL2, & Docker |
| **Multi-Node Clustering** | 🟡 Partial | In-memory registry with node auth stubs; multi-node RPC transport is experimental |

---

## 2. WHAT IS ACTUALLY INSTALLED?

This table describes the current repository state verified by executable code and test suites:

| Component | Status | What it does | How it is started |
|---|---|---|---|
| **Backend API** | ✅ Installed | Serves state, tasks, security, skills, learning & WebSocket streams | `uvicorn backend.main:app` |
| **Frontend UI** | ✅ Installed | Provides operational dashboard, swarm visualizer, skills & learning center | `cd frontend && npm run dev` |
| **Swarm Engine** | ✅ Installed | Manages task queueing, knight assignment, zero-trust checks & scoring | Integrated into backend engine |
| **Security Engine** | ✅ Installed | Enforces zero-trust capability checks, approvals & audit logging | Integrated into backend engine |
| **Memory Graph** | ✅ Installed | SQLite/JSON persistent timeline, vector search stub & snapshots | Integrated into backend engine |
| **Skills Platform** | ✅ Installed | Typed skill lifecycle management, dependency resolution & readiness checks | Integrated into backend engine |
| **Learning Engine** | ✅ Installed | Evidence collection, proposal scoring, sandbox experiments & rollback | Integrated into backend engine |
| **MCP Server** | ✅ Installed | Exposes Model Context Protocol tool interfaces for external agents | Imported via `backend/integrations/mcp_server.py` |
| **Python SDK** | ✅ Installed | Client library for agent-to-Kingdom HTTP/REST interactions | `from sdk.kingdom_sdk import KingdomSDK` |
| **Docker Container** | ✅ Installed | Launches backend & frontend in isolated containerized environments | `docker-compose up --build` |

---

## 3. QUICK START

The shortest verified path from a fresh computer to a running Kingdom instance:

```bash
# 1. Clone repository
git clone https://github.com/wests-cmd/kingdom.git
cd kingdom

# 2. Run automated installer
./scripts/install.sh

# 3. Start backend runtime
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000 &

# 4. Start frontend Command Center
cd frontend && npm run dev
```

Open `http://localhost:3000` in your browser to access the Kingdom Command Center.

---

## 4. BEGINNER INSTALLATION GUIDE

If you are new to software setup, follow these step-by-step instructions:

1. **Prerequisites**: Install [Python 3.11/3.12](https://www.python.org/downloads/) and [Node.js 20+](https://nodejs.org/).
2. **Open Terminal / Command Prompt**: Navigate to the directory where you want Kingdom installed.
3. **Run the Installer Script**:
   ```bash
   bash scripts/install.sh
   ```
   *What this does*: It creates a isolated Python virtual environment (`venv`), installs required Python dependencies, installs frontend Node packages, and builds the UI bundle.
4. **Start the System**:
   - Terminal 1 (Backend): `source venv/bin/activate && uvicorn backend.main:app --port 8000`
   - Terminal 2 (Frontend): `cd frontend && npm run dev`
5. **Verify**: Open `http://localhost:8000/status` in your browser. You should receive a JSON response confirming runtime status.

---

## 5. DETAILED INSTALLATION PATHS

### Method A: Automated Installer
```bash
./scripts/install.sh
```

### Method B: Manual Installation
```bash
# 1. Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install backend dependencies
pip install -r requirements.txt

# 3. Install frontend dependencies and build
cd frontend
npm install
npm run build
cd ..

# 4. Verify installation
python3 -m pytest
```

### Method C: Docker & Docker Compose
```bash
# Build and launch backend & frontend containers
docker-compose up --build -d

# View logs
docker-compose logs -f

# Shutdown
docker-compose down
```

---

## 6. CONFIGURATION

Kingdom reads configuration from `configs/` and environment variables.

- `configs/default.yaml`: Base system settings, logging, and storage paths.
- `configs/control_levels.yaml`: Autonomous governance control levels (L0 to L5).
- `configs/runtime.yaml`: Default model and execution parameters.
- `.env.example`: Template for environment-specific secrets.

> **Security Rule:** Never commit real API keys, passwords, or private tokens to Git repositories. Copy `.env.example` to `.env` for local configuration.

---

## 7. SECURITY & GOVERNANCE AUTHORITY HIERARCHY

Kingdom strictly enforces human authority over model execution:

```
HUMAN AUTHORITY (Admin / Approver)
        │
        ▼
GOVERNANCE POLICIES (Control Levels L0-L5)
        │
        ▼
SECURITY ENGINE (Zero-Trust & Capability Authorization)
        │
        ▼
EXECUTION LAYER (Sandboxed Runtime)
        │
        ▼
MODELS & LLMS (Inference Engines)
        │
        ▼
RETRIEVED / UNTRUSTED CONTEXT
```

- **Zero-Trust Capabilities**: High-risk capabilities (e.g. `filesystem.delete`, `process.execute`) require explicit human approval via `/security/approvals`.
- **Prompt Firewall**: Inspects inputs for injection attempts before processing.
- **Learning Safety**: The learning engine creates evidence and proposals; it **never** grants itself permissions or bypasses governance policies.

---

## 8. AI MAPS & SKILL INTELLIGENCE

### What is an AI Map?
An AI Map is a structured intelligence graph representing learned relationships, workflows, capability requirements, and routing outcomes across Kingdom subsystems.

### AI Map & Skill Map Structure
```
AI MAP / SKILL MAP
├── Metadata & Provenance
├── Required Dependencies & Capabilities
├── Required Tools & Models
├── Granted Permissions Boundary
└── Process & Specialization Graph
```

### Safety & Import Rules
Imported Skill Maps must **never** automatically receive elevated execution privileges. Every skill must pass:
1. Integrity & Provenance Verification
2. Dependency Resolution
3. Readiness Check ("DO I HAVE EVERYTHING?")
4. Governance Approval

### Community & Review
Join the Kingdom Skill Map Community on Discord for sharing and reviewing Skill Maps:
👉 **[Kingdom Discord Community](https://discord.gg/hNQFcVreg)**

---

## 9. COMMAND REFERENCE

- **Start Backend**: `uvicorn backend.main:app --port 8000`
- **Start Frontend**: `cd frontend && npm run dev`
- **Run Backend Tests**: `python3 -m pytest`
- **Build Frontend Bundle**: `npm --prefix frontend run build`
- **Run Installer Verification**: `bash scripts/install.sh`

---

## 10. TROUBLESHOOTING

- **Backend fails to start (`ModuleNotFoundError`)**: Ensure virtual environment is activated (`source venv/bin/activate`) and `pip install -r requirements.txt` was run.
- **Frontend build fails (`vite: not found`)**: Run `cd frontend && npm install` to install local build tooling.
- **Port 8000 / 3000 already in use**: Kill existing process using `kill $(lsof -t -i:8000)` or specify a custom port (`--port 8001`).

---

## 11. LICENSE & POLICIES

Kingdom is licensed under the **Apache License 2.0**. See the [LICENSE](LICENSE) file for complete license terms.

Commercial and enterprise usage guidelines are detailed in [COMMERCIAL_USE.md](COMMERCIAL_USE.md).
