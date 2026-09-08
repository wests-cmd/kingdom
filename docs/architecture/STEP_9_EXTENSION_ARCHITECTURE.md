# Step 9 — Extension Platform Architecture

## Overview

Kingdom's Extension Platform provides a sandboxed, capability-gated runtime environment allowing third-party tools, adapters, and event integrations to extend Kingdom without compromising core system security or stability.

```text
EXTENSION MANIFEST (manifest.json)
 ↓
MANIFEST VALIDATOR (ExtensionManifestValidator)
 ↓
REGISTRY (ExtensionRegistry State Machine)
 [ DISCOVERED -> INSTALLED -> ENABLED -> QUARANTINED -> REVOKED ]
 ↓
SANDBOX (ExtensionSandbox Exception & Error Threshold Isolation)
 ↓
TOOL REGISTRY (ExtensionToolRegistry Capability & Schema Checks)
 ↓
EVENT BUS (ExtensionEventBus Capability-Scoped Rate Limited Bus)
 ↓
LIFECYCLE MANAGER (ExtensionLifecycleManager Side-by-side Updates & Rollbacks)
```

---

## Extension State Machine

All extension instances transition through explicit states in `ExtensionRegistry` (`backend/extensions/registry.py`):

1. **`DISCOVERED`**: Manifest parsed and verified; not yet installed.
2. **`INSTALLED`**: Validated and installed; inactive until enabled.
3. **`ENABLED`**: Active and authorized to execute tools and consume subscribed events.
4. **`DISABLED`**: Manually deactivated by human supervisor; tool execution blocked.
5. **`QUARANTINED`**: Automatically isolated due to error threshold breaches (`>= 3` sandbox errors).
6. **`REVOKED`**: Permanently revoked due to security policy violations or administrative action.

---

## Tool Execution Pipeline

Tool execution requests undergo zero-trust validation before invocation:

```text
Tool Invocation Request
 ↓
Registry Lookup (Find active tool in ExtensionToolRegistry)
 ↓
Caller Permission Check (Verify caller has required_permissions)
 ↓
Input Schema Validation (Verify required parameters present)
 ↓
Sandbox Execution (Execute in ExtensionSandbox with error monitoring)
 ↓
Output Serialization & Audit Log
```

---

## Side-by-Side Version Updates & Instant Rollback

Extensions support side-by-side version updates (`ExtensionLifecycleManager`):
- New manifests are validated and installed side-by-side without mutating the existing active version.
- Version history preserves prior manifests (`version_history`).
- If health checks fail or regressions occur, `rollback_extension(extension_id, target_version)` restores the exact previous manifest version instantly.
