# Kingdom Integration Security Model

## Core Security Invariants

1. **Credential Brokerage Isolation**: Raw OAuth tokens, API keys, and certificates are handled exclusively by `CredentialBroker` (`backend/security/credential_broker.py`). Handles are opaque strings (`cred_handle_*`).
2. **LLM Sanitization**: All integration payloads passed to models or external callers are scrubbed for sensitive bearer tokens and secrets via `sanitize_payload_for_llm`.
3. **Capability Boundary Enforcement**: Tool invocation is allowed only when actor possesses all required capabilities and permissions.
4. **Mutating Action Approval Gates**: Any integration tool that mutates state (e.g., `github.issues.create`) requires explicit human approval (L4 gate).
5. **Terminal Revocation**: Revoking an integration immediately sets health to `REVOKED` and rejects further execution calls.
