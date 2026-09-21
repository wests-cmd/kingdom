# KINGDOM v40.2.0 — Distributed AI Runtime & Orchestration Infrastructure

[![Backend CI](https://github.com/wests-cmd/kingdom/actions/workflows/ci.yml/badge.svg)](https://github.com/wests-cmd/kingdom/actions)
[![License: CYA v2.0](https://img.shields.io/badge/License-CYA_v2.0-red.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](requirements.txt)
[![Node Version](https://img.shields.io/badge/node-20%20%7C%2024-green)](frontend/package.json)

Kingdom (`wests-cmd/kingdom`) is the core distributed runtime and infrastructure layer for the Centipede ecosystem. It provides distributed task execution, swarm orchestration, zero-trust capability security, persistent memory, typed AI skill intelligence, continuous learning, and live operational APIs.

---

## 1. INSTALL KINGDOM

Kingdom provides packaged installation paths for normal end-users, developers, servers, and production Docker environments.

### 🟢 Normal User — Kingdom Desktop App

**Zero-Dependency Experience:**
Normal users do NOT need to install Python, Node.js, or npm. The packaged Kingdom Desktop application bundles a standalone native backend executable and precompiled frontend static assets.

1. Download the Kingdom Desktop package for your operating system from GitHub Release Artifacts.
2. Launch **Kingdom**.
3. The desktop shell automatically starts the bundled backend runtime and loads the Command Center UI.

| Platform | Package Format | Status | Build Artifact |
|---|---|---|---|
| **Linux** | `AppImage` | 🟢 Available | `Kingdom-40.2.0.AppImage` |
| **Linux** | `DEB` | 🟢 Available | `kingdom-desktop_40.2.0_amd64.deb` |
| **Windows** | `NSIS` | 🟢 Supported | `Kingdom-Setup-40.2.0.exe` |
| **macOS** | `DMG` | 🟢 Supported | `Kingdom-40.2.0.dmg` |

#### What "One-Click Download and Deployment" Means and How It Works
A "one-click download and deployment" is a process where a user can install and run an application with a single action — often by clicking a link or button — without manual setup, multiple steps, or administrative rights.

##### In Desktop & Application Contexts
In desktop environments, deployment automation allows developers to publish self-updating applications that install and run with minimal user interaction:
- **Manifest download** – The system first retrieves a deployment manifest describing the app version, update behavior, publisher, and update location.
- **Check for updates** – Kingdom compares the manifest to the installed version and downloads only changed files.
- **Isolated installation** – The application installs per-user in an isolated location without affecting other apps or requiring elevated admin rights.
- **Execution** – The application runs from its installed location, even offline, and automatically checks for updates in the background.

##### In Modern DevOps & Cloud Contexts
In automated cloud and container environments, a single action triggers an entire pipeline:
1. Pulling code from the repository
2. Detecting framework requirements & dependencies
3. Compiling production frontend and backend binaries
4. Provisioning runtimes and container networks
5. Configuring SSL and routing
6. Launching application instances and executing readiness health checks

##### Key Benefits
- **Minimal User Effort** – Single action installs and runs the application.
- **Automatic Updates** – Only changed files are downloaded; no manual patching needed.
- **Low System Impact** – Isolated per-user installs prevent system conflicts.
- **No Admin Rights Required** – Standard user accounts can run the application seamlessly.
- **Repeatable Automation** – Entire deployment pipelines run automatically and reliably.

---

### 🛠️ Developer Installation

*For developers and contributors modifying Kingdom source code.*

```bash
# 1. Clone repository
git clone https://github.com/wests-cmd/kingdom.git
cd kingdom

# 2. Run automated setup script
./scripts/install.sh

# 3. Start backend runtime
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000 &

# 4. Start frontend Command Center
cd frontend && npm run dev
```

---

### 💻 Advanced / Server Installation

```bash
# Manual Python Virtual Environment Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Production Frontend Build
cd frontend
npm install
npm run build
cd ..

# Verify Installation
python3 -m pytest
```

---

### 🐳 Docker / Container Installation

```bash
# Build and launch production multi-node topology (Commander, Knight Coder, Knight Memory)
docker-compose up --build -d

# View logs
docker-compose logs -f

# Shutdown
docker-compose down
```

---

## 2. WHAT GETS INSTALLED?

| Component | Purpose | Installed by default? | Status |
|---|---|---|---|
| **Kingdom Desktop** | Graphical desktop launcher & process manager | Yes | 🟢 Implemented |
| **Command Center UI** | Operational web dashboard & visualizer (`frontend/`) | Yes | ✅ Implemented |
| **Commander / Backend API** | FastAPI core runtime & REST/WS endpoints | Yes | ✅ Implemented |
| **Knight Swarm Engine** | Task queueing, knight specialization & execution | Yes | ✅ Implemented |
| **Zero-Trust Security** | Capability authorizations, approvals & prompt firewall | Yes | ✅ Implemented |
| **Memory Graph** | Timeline persistence, vector search & snapshots | Yes | ✅ Implemented |
| **Skills Platform** | Typed skill lifecycle, dependencies & readiness engine | Yes | ✅ Implemented |
| **Learning Engine** | Evidence collection, proposals, experiments & rollback | Yes | ✅ Implemented |
| **MCP Server** | Model Context Protocol tool contracts for external agents | Yes | ✅ Implemented |
| **Python SDK** | Client library for agent-to-Kingdom HTTP/REST calls | Yes | ✅ Implemented |

---

## 3. IMPLEMENTATION STATUS

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
| **Installer Script** | ✅ Implemented | Hardened `scripts/install.sh` supporting Linux, macOS, Windows/WSL2, & Docker |
| **Desktop Launcher Foundation** | ✅ Implemented | `desktop/launcher.js` manages bundled backend startup, readiness polling (`/health/ready`), and webview window launch |
| **Multi-Node Clustering & Node Federation** | ✅ Implemented | Ed25519 identity keypairs, persistent node registry, single-use pairing codes, mutual authentication, signed Ed25519 RPC transport, capability-based authorization, node revocation, heartbeat health engine, and Command Center UI |

---

## 4. CONFIGURATION

Kingdom reads configuration from `configs/` and environment variables.

- `configs/default.yaml`: Base system settings, logging, and storage paths.
- `configs/control_levels.yaml`: Autonomous governance control levels (L0 to L5).
- `configs/runtime.yaml`: Default model and execution parameters.
- `.env.example`: Template for environment-specific secrets.

> **Security Rule:** Never commit real API keys, passwords, or private tokens to Git repositories. Copy `.env.example` to `.env` for local configuration.

---

## 5. COMMAND REFERENCE

- **Start Backend**: `uvicorn backend.main:app --port 8000`
- **Start Frontend**: `cd frontend && npm run dev`
- **Run Backend Tests**: `python3 -m pytest`
- **Build Desktop Release**: `cd desktop && npm run build`
- **Run Installer Verification**: `bash scripts/install.sh`

---

## 6. OFFICIAL LICENSE & COMMERCIAL USE POLICY

Kingdom is distributed under the custom **CYA License v2.0** ([Kingdom License](./LICENSE)).

### Key License Provisions:
1. **Personal & Educational Grant**: Permission is granted to use, copy, modify, and distribute the Software for personal, educational, and non-commercial purposes.
2. **Commercial Restrictions**: Commercial use (selling, sublicensing, paid products/services, revenue-generating systems) is strictly prohibited without prior written approval.
3. **Commercial Approval**: To request commercial licensing approval, contact the copyright holder via GitHub (`https://github.com/wests-cmd`).
4. **Authoritative Terms**: Read the complete, authoritative legal terms in the root [LICENSE](./LICENSE) file and commercial policy guidelines in [COMMERCIAL_USE.md](./COMMERCIAL_USE.md).
