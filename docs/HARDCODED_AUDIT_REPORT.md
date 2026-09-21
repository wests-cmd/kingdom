# Kingdom v40.2.0 — Hard-Coded & Fabricated Values Audit Report

## Executive Summary
This audit inspects Kingdom v40.2.0 for hard-coded runtime fallbacks, fabricated hardware defaults, automatic demo skill injections, and mock AI responses. It documents the fixes applied to enforce Strict Truth Mode (`STRICT_TRUTH_MODE=true`) and clean production startup behavior.

---

## 1. Audit Findings & Corrective Actions

### A. Fabricated Hardware Fallbacks (`backend/api.py`)
- **Finding:** System check endpoint `GET /system/check` contained fallback values `4.0` GB total memory and `2.0` GB available memory if `psutil.virtual_memory()` returned `None`.
- **Correction:** Replaced synthetic fallback values with `None`. System check now reports `null` when memory metrics cannot be probed, preventing false hardware reporting.

### B. Fallback Version Defaults (`backend/api.py`)
- **Finding:** `GET /api/system/version` fell back to `"40.2.0"` if `STATE.get("version")` was empty.
- **Correction:** Changed default fallback to `"unknown"`. Version truth is initialized at runtime startup.

### C. Automatic Demo Skill Injection (`backend/api.py`)
- **Finding:** Startup in `backend/api.py` automatically instantiated, saved, installed, and activated `skill-web-research`.
- **Correction:** Removed automatic demo skill injection from production startup. Created explicit demo bootstrap script `scripts/bootstrap_demo.py` for demo environment evaluation.

### D. Explicit Runtime Modes & Strict Truth Mode
- **Feature Added:** Supported `KINGDOM_MODE` environment variable (`production`, `development`, `demo`). Exposed `mode` attribute in `GET /api/system/version`.
- **Feature Added:** Supported `STRICT_TRUTH_MODE=true` environment variable. When enabled, Kingdom outputs `null` / `unknown` / `unavailable` rather than synthetic fallbacks.

### E. AI Model Generation Pathway (`backend/api.py`, `backend/models/service.py`)
- **Finding Audit:** `POST /models/generate` delegates directly to `ModelService.generate()`. If no provider (e.g., Ollama / OpenAI) is configured, it raises HTTP 503 Service Unavailable ("No model provider configured") rather than returning simulated responses.

---

## 2. Strict Truth Verification Matrix

| Area | Former Behavior | Corrected Production Behavior | Verification Method |
|---|---|---|---|
| Hardware Memory Probing | Defaulted to 4.0GB / 2.0GB | Reports `null` if unprobeable | `GET /system/check` |
| Version Defaulting | Fallback to "40.2.0" | Fallback to "unknown" | `GET /api/system/version` |
| Production Skills | Auto-injected `skill-web-research` | Starts clean (0 skills) | `GET /skills` |
| Runtime Mode | Implicit | Explicit `KINGDOM_MODE` | `GET /api/system/version` |
| Model Generation | Explicit 503 on missing provider | Explicit 503 on missing provider | `POST /models/generate` |

---

## 3. Conclusion
Kingdom v40.2.0 now operates under strict data truth. No synthetic memory values or ungranted demo skills are auto-injected in production.
