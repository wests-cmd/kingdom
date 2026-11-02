# Adapter Capability Discovery & Beginner Setup Readiness

This document describes the external tool adapter capability discovery layer, Agent Client Protocol (ACP) support distinctions, model readiness tracking, and beginner setup workflows in Kingdom.

---

## 1. Architectural Scope & Security Boundaries

Kingdom provides a model-neutral, protocol-aware discovery layer for external coding assistants and language engines:

- **Strict Credential Isolation:** Kingdom **never** extracts browser cookies, keychain passwords, or other applications' session tokens. External tools manage their own authentication locally.
- **Accurate Protocol & Capability Representation:** Tools and models report only their verified capabilities and protocols (e.g. native `acp`, `cli_wrapper`, or `http_api`). Kingdom does not assume universal tool calling, vision support, or ACP compatibility across all engines.
- **Explicit Unavailable Reasons:** If an engine executable is missing from the system `PATH` or unauthenticated, it is marked with clear, actionable `unavailable_reasons`.
- **Level 5 Owner Protection:** REST discovery endpoints (`/integrations/adapters`) require authenticated Level 5 owner credentials via `require_owner`.

---

## 2. Supported Tools and Adapters

| Adapter ID | Name | Protocol | ACP Native | Executable | Required Permissions |
|---|---|---|---|---|---|
| `codex` | OpenAI Codex CLI | `acp` | Yes | `codex` | `filesystem.read`, `filesystem.write`, `process.execute` |
| `claude_code` | Anthropic Claude Code | `cli_wrapper` | No | `claude` | `filesystem.read`, `filesystem.write`, `process.execute` |
| `gemini_cli` | Google Gemini CLI | `cli_wrapper` | No | `gemini` | `filesystem.read`, `process.execute` |
| `jules` | Kingdom Native Jules Adapter | `acp` | Yes | `jules` | `filesystem.read`, `filesystem.write`, `process.execute` |
| `ollama` | Ollama Local Engine | `http_api` | No | `ollama` | `process.execute`, `network.access` |

---

## 3. Supported Model Profiles

Model profiles describe exact execution parameters, context window limits, and capability flags:

- `chatgpt-4o`: Cloud reasoning and multimodal analysis (128k context, tools, vision).
- `ollama-qwen-coder`: Local coding completion and editing (32k context, tools, local execution).
- `ollama-llama3`: General-purpose local reasoning (131k context, tools, local execution).
- `gemini-1.5-pro`: Cloud ultra-long context reasoning (1M context, tools, vision).

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
- **Setup:** Local daemon listening on `http://localhost:11434`. No account login required.

### Native Jules Adapter
- **Installation:** Native Kingdom supervisor integration in `backend/integrations/jules.py`.
- **Sign-in:** Owner authorization key configured in `data/secrets/jules.key` (mode `0o600`).

---

## 5. REST API Reference

All endpoints require owner authentication headers (`Authorization: Bearer <owner_token>`).

- `GET /integrations/adapters`: Returns lists of all supported tools and model profiles with installation status and capability tags.
- `GET /integrations/adapters/{tool_id}`: Returns detailed inspection of a specific tool, including beginner setup guide and unavailable reasons.
- `GET /integrations/adapters/{tool_id}/connectivity`: Validates executable presence and connectivity status.
