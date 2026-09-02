# AGENTS.md — Kingdom Developer & AI Agent Guidelines

## 1. Repository Purpose
Kingdom (`wests-cmd/kingdom`) is the core distributed runtime and infrastructure layer for the Centipede ecosystem. It handles distributed task execution, swarm orchestration, zero-trust security, persistent memory, and live operational APIs.

Sledge sits above Kingdom as the user-facing agent. Do NOT move product-level user interaction logic into Kingdom.

---

## 2. Architectural Principles & Authority Hierarchy
Kingdom strictly enforces human authority over model execution:

1. **Human Authority**
2. **Governance Policies**
3. **Security Engine**
4. **Execution Layer**
5. **Models / LLMs**
6. **Retrieved / Untrusted Context**

### Core Directives:
- Models propose actions; the execution layer validates authority, capabilities, and human approvals before execution.
- Default to **deny-by-default**.
- High-risk operations (e.g. `filesystem.delete`, `process.execute`, `docker.execute`) MUST require human approval.
- Mocks are NEVER permitted in production runtime paths.

---

## 3. Test & Build Commands
- **Backend Tests**: `python3 -m pytest`
- **Frontend Build**: `npm --prefix frontend run build` or `cd frontend && npm install && npm run build`
- **Start Backend**: `uvicorn backend.main:app --reload`
- **Start Frontend**: `cd frontend && npm run dev`

---

## 4. Coding & API Conventions
- Use typed models / Pydantic schemas for API inputs and outputs.
- Store persistent runtime state, tasks, knights, events, and memory in SQLite (`data/kingdom.db`).
- Mask sensitive credentials (`api_key`, `secret`, `token`, `password`) in audit logs (`data/logs/audit.jsonl`).
- Publish all state changes to `EventBus` (`backend/events/event_bus.py`).
