# AGENTS.md — Kingdom Developer & AI Agent Guidelines

## 1. Repository Purpose
Kingdom (`wests-cmd/kingdom`) is an adaptive AI harness and distributed runtime for completing tasks across models, agents, tools and approved clusters of computers. It can stand alone or support the Centipede ecosystem. Its core is plan → place → execute → verify → remember → adapt, with persistent evidence and human authority.

Kingdom provides its own user-facing harness. Sledge, Hermes, Claude-style CLIs and other agents are optional adapters, not required identities or dependencies. Develop cluster orchestration and evidence-based adaptation alongside the interface; do not reduce the product to model chat or assume all tools execute on the controller. Keep implementation claims distinct from roadmap goals. See docs/ADAPTIVE_CLUSTER_CORE.md.

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
- High-risk operations require human approval at levels 0–4. At level 5, the authenticated owner’s policy selection is standing authorization for granted tools; task/model metadata cannot elevate policy or capabilities. OS permission boundaries remain mandatory.
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
