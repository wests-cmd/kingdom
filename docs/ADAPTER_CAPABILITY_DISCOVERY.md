# Adapter Capability Discovery & Beginner Setup Readiness

This document describes the external tool adapter capability discovery layer, Agent Client Protocol (ACP) support distinctions, model readiness tracking, and beginner setup workflows in Kingdom.

---

## 1. Architectural Scope & Security Boundaries

Kingdom provides a model-neutral, protocol-aware discovery layer for external coding assistants and language engines:

- **Strict Credential Isolation:** Kingdom **never** extracts browser cookies, keychain passwords, or other applications' session tokens. External tools manage their own authentication locally.
- **Accurate Protocol & Capability Representation:** Tools and models report catalog hints and observed facts truthfully. Documented protocol support (e.g., ACP) is not returned as verified runtime compliance without protocol negotiation. Kingdom does not assume universal tool calling, vision support, or ACP compatibility across all engines.
- **No Binary Execution During Inspection:** Discovered binaries in system PATH are never executed merely to inspect or test them. Presence in PATH alone does not prove connectivity, authentication, daemon readiness, model weights, or planner readiness.
- **Explicit Unavailable Reasons:** If an engine executable is missing from the system `PATH`, unauthenticated, or unhandshaked, it is marked with clear, actionable `unavailable_reasons`.
- **Configured vs. Verified Availability:** Sourcing a model profile or native Jules configuration does not promote the entity to ready, connected, authenticated, or available. Unverified items remain explicitly `available=False` with bounded reasons.
- **Strictly Read-Only Discovery:** Discovery endpoints execute read-only projections over existing SQLite tables (`sqlite_master` existence checks). They **never** instantiate services (such as `JulesService`, `ModelProfiles`, or `ChatGPTPlanConnection`) that run schema migrations (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`) or generate vault encryption keys on disk.
- **No Decryption or Ciphertext Access:** Discovery routines never read ciphertext blobs, decrypt credentials, or inspect refresh tokens.
- **Separation of Catalog Templates & Model Selections:** Catalog templates (e.g., `chatgpt-4o`) never inherit availability from an unrelated configured ChatGPT selection (such as `gpt-6-sol` or `gpt-6.1-sol`). Actual configured selections are surfaced distinctly, with live inference explicitly separated from configuration and remaining unverified (`available=False`).
- **Owner Authentication Protection:** REST discovery endpoints (`/integrations/adapters`) authenticate the owner identity and trusted request origin via `require_owner`. `require_owner` authenticates owner and origin for the control plane; it does not check or elevate the autonomy policy level (which remains bound to execution governance). Discovery does not grant execution authority.
- **Concrete Pydantic Schema Contracts:** All API response contracts adhere to concrete Pydantic schemas (`AdapterListResponse`, `ToolInspectionResponse`, `ToolConnectivityResponse`, `DiscoveredModel`) rather than generic dictionaries.

---

## 2. Supported Tools and Adapters

| Adapter ID | Name | Protocol | ACP Documented | Executable | Required Permissions |
|---|---|---|---|---|---|
| `codex` | OpenAI Codex CLI | `acp` | Yes | `codex` | `filesystem.read`, `filesystem.write`, `process.execute` |
| `claude_code` | Anthropic Claude Code | `cli_wrapper` | No | `claude` | `filesystem.read`, `filesystem.write`, `process.execute` |
| `gemini_cli` | Google Gemini CLI | `cli_wrapper` | No | `gemini` | `filesystem.read`, `process.execute` |
| `jules` | Kingdom Native Jules Adapter | `acp` | Yes | (native service) | `filesystem.read`, `filesystem.write`, `process.execute` |
| `ollama` | Ollama Local Engine | `http_api` | No | `ollama` | `process.execute`, `network.access` |

---

## 3. Supported Model Profiles & Configured Inventory

Model inventory separates configured model profiles from catalog reference templates:

- **Configured Model Profiles:** Sourced dynamically from `model_profiles` in SQLite without running schema migrations. Reports user-configured endpoints, context windows, tools, vision capabilities, and credential presence (`has_credentials`). Configured profiles remain unverified (`available=False`) until bounded live health/inference checks succeed.
- **Configured ChatGPT Plan Connection:** Read directly from `chatgpt_plan_meta` and `chatgpt_plan_accounts`. If a model like `gpt-6-sol` is configured, it is surfaced as a configured ChatGPT model with explicit notice that inference is unverified without a live provider call.
- **Catalog Reference Templates:** Reference specifications for known models (`chatgpt-4o`, `ollama-qwen-coder`, `ollama-llama3`, `gemini-1.5-pro`). Marked unavailable with clear reasons if the provider daemon, weights, or matching account connection are missing. Crucially, `chatgpt-4o` does not become available when `gpt-6-sol` is configured.

---

## 4. Beginner Setup Readiness & Sign-in Guide

Each adapter manifest includes a `beginner_setup_guide` detailing non-destructive installation and authentication hints:

### Codex CLI
- **Installation:** `npm install -g @openai/codex`
- **Sign-in:** Run `codex login` in your terminal. Auth tokens stay within OpenAI's user profile directories.

### Anthropic Claude Code
- **Installation:** `npm install -g @anthropic-ai/claude-code`
- **Sign-in:** Run `claude login` directly in your host terminal.

### Google Gemini CLI
- **Installation:** Install Google Cloud SDK or Gemini CLI utility.
- **Sign-in:** Run `gcloud auth application-default login` or export `GEMINI_API_KEY`.

### Ollama Local Engine
- **Installation:** Download and install from [ollama.com](https://ollama.com).
- **Setup:** Local daemon listening on `http://localhost:11434`. No account login required. Model weights must be pulled locally.

### Native Jules Adapter
- **Installation:** Native Kingdom supervisor integration in `backend/integrations/jules.py`.
- **Sign-in:** Requires owner key configured in `data/secrets/jules.key` (mode `0o600`) and Level 5 standing authorization for cloud dispatch.

---

## 5. REST API Reference

All endpoints require owner authentication headers (`Authorization: Bearer <owner_token>`) from a trusted origin.

- `GET /integrations/adapters`: Returns `AdapterListResponse` containing lists of all supported tools and model profiles with observed installation status, protocol verification state, and capability tags.
- `GET /integrations/adapters/{tool_id}`: Returns `ToolInspectionResponse` with detailed inspection of a specific tool, including beginner setup guide and unavailable reasons.
- `GET /integrations/adapters/{tool_id}/connectivity`: Returns `ToolConnectivityResponse` reporting connectivity, installation, ACP compliance, protocol verification, and planner availability status without executing binaries.
