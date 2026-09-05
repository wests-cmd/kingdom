# KINGDOM v40.2 — Distributed AI Runtime & Orchestration Infrastructure

[![Backend CI](https://github.com/wests-cmd/kingdom/actions/workflows/ci.yml/badge.svg)](https://github.com/wests-cmd/kingdom/actions)
[![License: CYA v2.0](https://img.shields.io/badge/License-CYA_v2.0-red.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](requirements.txt)
[![Node Version](https://img.shields.io/badge/node-20%20%7C%2024-green)](frontend/package.json)

Kingdom (`wests-cmd/kingdom`) is the core distributed runtime and infrastructure layer for the Centipede ecosystem. It provides distributed task execution, swarm orchestration, zero-trust capability security, persistent memory, typed AI skill intelligence, continuous learning, and live operational APIs.

> **Architectural Separation:** Sledge sits above Kingdom as the user-facing agent layer. Kingdom operates strictly as the underlying runtime infrastructure, providing security boundaries, execution sandboxing, and node coordination.

---

## 1. INSTALL KINGDOM

Kingdom is designed so normal users can run Kingdom from a graphical desktop application without opening a terminal.

### 🔵 Recommended — Kingdom Desktop App (In Development)

> **Status: Planned / In Active Development**
> *The Desktop App installer wrapper (`Kingdom-Setup.exe` / `.dmg` / AppImage) is currently under active development. Developers can use the Developer Installation instructions below.*

**Intended Normal User Experience:**
1. Download the Kingdom Desktop Installer for your operating system.
2. Run the graphical installation wizard.
3. Launch **Kingdom** from your desktop or application menu.
4. Kingdom automatically starts local backend runtime services and loads the Command Center.
5. Complete first-run setup in the graphical wizard.

| Platform | Installer Format | Status |
|---|---|---|
| **Windows** | `Kingdom-Setup.exe` | 🔵 In Development |
| **macOS** | `Kingdom.dmg` | 🔵 In Development |
| **Linux** | `Kingdom.AppImage` | 🔵 In Development |

---

### 🛠️ Developer Installation

*This method is intended for software developers and contributors working directly with the source code.*

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
# Build and launch backend & frontend containers
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
| **Kingdom Desktop** | Graphical desktop launcher & process manager | Planned | 🔵 In Development |
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
| **Desktop Installer Wrapper** | 🔵 Planned | Self-contained desktop app bundler launching local backend & web view automatically |
| **Multi-Node Clustering & Node Federation** | 🟢 Implemented | Ed25519 identity keypairs, persistent node registry, single-use pairing codes & QR codes, mutual authentication, signed RPC transport, capability-based authorization, node revocation, health engine, and Command Center Nodes UI |

---

## 4. DESKTOP ROADMAP

1. **Phase 1 — Desktop Launcher**: Self-contained application launcher process.
2. **Phase 2 — Bundled Runtime**: Single-package distribution bundling Python & Node runtimes.
3. **Phase 3 — Automatic Lifecycle**: Automated background startup and clean process shutdown.
4. **Phase 4 — Graphical Setup**: First-run configuration wizard in UI.
5. **Phase 5 — Native Installers**: One-click installers for Windows (`.exe`), macOS (`.dmg`), and Linux (`AppImage`).
6. **Phase 6 — Auto Updates**: Background update checks for core runtime assets.
7. **Phase 7 — System Tray**: Menu bar indicator and service controls.
8. **Phase 8 — Graphical Skill Management**: Drag-and-drop Skill Map package installer in Command Center.
9. **Phase 9 — Visual Trust Review**: Permission review UI for imported Skill Maps.

---

## 5. CONFIGURATION

Kingdom reads configuration from `configs/` and environment variables.

- `configs/default.yaml`: Base system settings, logging, and storage paths.
- `configs/control_levels.yaml`: Autonomous governance control levels (L0 to L5).
- `configs/runtime.yaml`: Default model and execution parameters.
- `.env.example`: Template for environment-specific secrets.

> **Security Rule:** Never commit real API keys, passwords, or private tokens to Git repositories. Copy `.env.example` to `.env` for local configuration.

---

## 6. SECURITY & GOVERNANCE AUTHORITY HIERARCHY

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

## 7. AI MAPS & SKILL INTELLIGENCE

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

### Kingdom AI Skill Map Packet
Official example specification manifests and guidelines are provided in [`skills/kingdom-ai-skill-map-packet/`](skills/kingdom-ai-skill-map-packet/).

### Safe Upload & Review Guidelines
- Skill Maps must **never** contain API keys, passwords, tokens, private memory dumps, or destructive payloads.
- Users may upload Skill Maps to ChatGPT or AI assistants for structural/security review before importing.
- AI review does **not** grant execution trust; all imported skills remain subject to Kingdom zero-trust sandbox boundaries.

### Community & Review
Join the Kingdom Skill Map Community on Discord for sharing and reviewing Skill Maps:
👉 **[Kingdom Discord](https://discord.gg/hNQFcVreg)**

---

## 8. COMMAND REFERENCE

- **Start Backend**: `uvicorn backend.main:app --port 8000`
- **Start Frontend**: `cd frontend && npm run dev`
- **Run Backend Tests**: `python3 -m pytest`
- **Build Frontend Bundle**: `npm --prefix frontend run build`
- **Run Installer Verification**: `bash scripts/install.sh`

---

## 9. TROUBLESHOOTING

- **Backend fails to start (`ModuleNotFoundError`)**: Ensure virtual environment is activated (`source venv/bin/activate`) and `pip install -r requirements.txt` was run.
- **Frontend build fails (`vite: not found`)**: Run `cd frontend && npm install` to install local build tooling.
- **Port 8000 / 3000 already in use**: Kill existing process using `kill $(lsof -t -i:8000)` or specify a custom port (`--port 8001`).

---

## 10. OFFICIAL LICENSE & COMMERCIAL USE POLICY

Kingdom is distributed under the custom **CYA License v2.0** ([Kingdom License](./LICENSE)).

### Key License Provisions:
1. **Personal & Educational Grant**: Permission is granted to use, copy, modify, and distribute the Software for personal, educational, and non-commercial purposes.
2. **Commercial Restrictions**: Commercial use (selling, sublicensing, paid products/services, revenue-generating systems) is strictly prohibited without prior written approval.
3. **Commercial Approval**: To request commercial licensing approval, contact the copyright holder via GitHub (`https://github.com/wests-cmd`).
4. **Authoritative Terms**: Read the complete, authoritative legal terms in the root [LICENSE](./LICENSE) file and commercial policy guidelines in [COMMERCIAL_USE.md](./COMMERCIAL_USE.md).
