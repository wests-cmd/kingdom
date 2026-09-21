# KINGDOM v1TAS (v1.0.0) — Distributed AI Runtime & Orchestration Infrastructure

[![Backend CI](https://github.com/wests-cmd/kingdom/actions/workflows/ci.yml/badge.svg)](https://github.com/wests-cmd/kingdom/actions)
[![License: CYA v2.0](https://img.shields.io/badge/License-CYA_v2.0-red.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](requirements.txt)
[![Node Version](https://img.shields.io/badge/node-20%20%7C%2024-green)](frontend/package.json)

Kingdom (`wests-cmd/kingdom`) is the core zero-trust distributed runtime and infrastructure layer for the Centipede ecosystem. It provides distributed task execution, swarm orchestration, capability security, persistent memory, typed AI skill intelligence, continuous learning, and live operational APIs.

**First Stable Release:** `Kingdom v1TAS`
**Canonical Version:** `1.0.0`
**Git Release Tag:** `v1.0.0`

---

## 1. INSTALL KINGDOM

Kingdom provides packaged installation paths for normal end-users, developers, servers, and production Docker environments.

### 🟢 Normal User — Kingdom Desktop App

**Zero-Dependency Experience:**
Normal users do NOT need to install Python, Node.js, or npm. The packaged Kingdom Desktop application bundles a standalone native backend executable (`kingdom-backend`) and precompiled frontend static assets.

1. Download the Kingdom Desktop package for your operating system from GitHub Release Artifacts.
2. Launch **Kingdom**.
3. The desktop shell automatically starts the bundled backend runtime and loads the Command Center UI.

| Platform | Package Format | Status | Build Artifact |
|---|---|---|---|
| **Linux** | `AppImage` | 🟢 Available | `Kingdom-1.0.0.AppImage` |
| **Linux** | `DEB` | 🟢 Available | `kingdom-desktop_1.0.0_amd64.deb` |
| **Windows** | `NSIS` | 🟢 Supported | `Kingdom-Setup-1.0.0.exe` |
| **macOS** | `DMG` | 🟢 Supported | `Kingdom-1.0.0.dmg` |

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

## 3. CONFIGURATION

Kingdom reads configuration from `configs/` and environment variables.

- `configs/default.yaml`: Base system settings, logging, and storage paths.
- `configs/control_levels.yaml`: Autonomous governance control levels (L0 to L5).
- `configs/runtime.yaml`: Default model and execution parameters.
- `.env.example`: Template for environment-specific secrets.

> **Security Rule:** Never commit real API keys, passwords, or private tokens to Git repositories. Copy `.env.example` to `.env` for local configuration.

---

## 4. OFFICIAL LICENSE & COMMERCIAL USE POLICY

Kingdom is distributed under the custom **CYA License v2.0** ([Kingdom License](./LICENSE)).

### Key License Provisions:
1. **Personal & Educational Grant**: Permission is granted to use, copy, modify, and distribute the Software for personal, educational, and non-commercial purposes.
2. **Commercial Restrictions**: Commercial use (selling, sublicensing, paid products/services, revenue-generating systems) is strictly prohibited without prior written approval.
3. **Commercial Approval**: To request commercial licensing approval, contact the copyright holder via GitHub (`https://github.com/wests-cmd`).
4. **Authoritative Terms**: Read the complete, authoritative legal terms in the root [LICENSE](./LICENSE) file and commercial policy guidelines in [COMMERCIAL_USE.md](./COMMERCIAL_USE.md).
