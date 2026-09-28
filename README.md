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

### 🟢 Normal User — Guided First-Run Setup & Desktop App

**Zero-Dependency Experience:**
Normal users do NOT need to install Python, Node.js, or npm. The packaged Kingdom Desktop application bundles a standalone native backend executable (`kingdom-backend`), precompiled frontend static assets, and an integrated **Guided First-Run Setup Wizard**.

#### First Launch Experience:
1. Download and launch **Kingdom**.
2. **Automatic Hardware Inspection:** Kingdom detects CPU cores, total RAM, OS architecture, GPU availability, and display mode without installing heavy external tools.
3. **Smart Profile Recommendation:** Kingdom recommends an optimal runtime profile based on your computer's specs:
   - **Developer Profile:** Recommended for standard coding/development tasks (Planner, Coder, Security Knights enabled).
   - **Research & Analysis Profile:** Focused on information gathering, web research, and persistent memory (Planner, Researcher, Memory Knights enabled).
   - **Full Swarm Profile:** Recommended for multi-core system with 8GB+ RAM (All 5 Knights enabled).
   - **Server / Headless Profile:** Recommended for server or low-memory environments (<4GB RAM or no display). Runs backend services without opening the graphical UI window.
   - **Custom Profile:** Manually select individual active Knights (Planner, Coder, Researcher, Memory, Security) and toggle the Command Center UI on/off.
4. **Profile Persistence:** Your setup choice is stored securely in per-user data (`<userData>/local_profile.json`).

| Platform | Package Format | Status | Build Artifact |
|---|---|---|---|
| **Linux** | `AppImage` | 🟢 Available | `Kingdom-1.0.0.AppImage` |
| **Linux** | `DEB` | 🟢 Available | `kingdom-desktop_1.0.0_amd64.deb` |
| **Windows** | `NSIS` | 🟢 Supported | `Kingdom-Setup-1.0.0.exe` |
| **macOS** | `DMG` | 🟢 Supported | `Kingdom-1.0.0.dmg` |

---

### ⚙️ LOCAL PROFILE MANAGEMENT & RESET

- **Profile Storage:** Your profile is stored at `<userData>/local_profile.json` (or `configs/local_profile.json` in standalone mode).
- **Resetting Your Setup:** To re-run the setup wizard or change your profile, delete `local_profile.json` or update its values.
- **Corrupt Profile Protection:** If `local_profile.json` is deleted or corrupted, Kingdom safely falls back to displaying the setup wizard (on desktop) or enabling all default Knights (on direct backend / server startup) without crashing.

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

### 💻 Direct Backend & Server Mode

Kingdom can be run directly from the command line without Electron or a desktop profile:

```bash
# Manual Python Virtual Environment Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start backend directly (defaults to all built-in Knights enabled)
python3 backend/main.py --host 127.0.0.1 --port 8000

# Or specify a custom profile path via environment variable:
KINGDOM_LOCAL_PROFILE=configs/local_profile.json python3 backend/main.py
```

---

### 🐳 Docker / Container Deployment

Docker and server environments run independently without requiring Electron or desktop profiles:

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
| **Kingdom Desktop Shell** | Native desktop launcher, guided wizard & process supervisor | Yes | 🟢 Implemented |
| **Command Center UI** | Operational web dashboard & visualizer (`frontend/`) | Yes | ✅ Implemented |
| **Commander / Backend API** | FastAPI core runtime & REST/WS endpoints | Yes | ✅ Implemented |
| **Knight Swarm Engine** | Profile-aware knight execution (Planner, Coder, Researcher, Memory, Security) | Yes | ✅ Implemented |
| **Zero-Trust Security** | Capability authorizations, approvals & prompt firewall | Yes | ✅ Implemented |
| **Memory Graph** | Timeline persistence, vector search & snapshots | Yes | ✅ Implemented |
| **Skills Platform** | Typed skill lifecycle, dependencies & readiness engine | Yes | ✅ Implemented |
| **Learning Engine** | Evidence collection, proposals, experiments & rollback | Yes | ✅ Implemented |
| **MCP Server** | Model Context Protocol tool contracts for external agents | Yes | ✅ Implemented |
| **Python SDK** | Client library for agent-to-Kingdom HTTP/REST calls | Yes | ✅ Implemented |

---

## 3. CONFIGURATION & CATALOGS

- `configs/install_profiles.json`: Read-only install profile catalog definition.
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
