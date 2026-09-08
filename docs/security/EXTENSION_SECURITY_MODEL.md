# Extension Platform Security Model

## Zero-Trust Isolation Architecture

Kingdom enforces a zero-trust, deny-by-default security model across all platform extensions. Extensions do not run with root permissions and cannot bypass backend governance boundaries.

---

## Prohibited Permission Boundaries

Extensions attempting to declare any prohibited permissions are automatically rejected during manifest validation (`ExtensionManifestValidator` in `backend/extensions/manifest_validator.py`):

- `kernel.bypass_security`
- `system.disable_audit`
- `governance.auto_approve`
- `root.escalate`

Any manifest containing these permissions raises `ManifestValidationError` and is blocked from discovery or installation.

---

## Capability-Gated Tool & Event Access

1. **Tool Execution:** Tools registered by extensions specify `required_permissions` (e.g. `network.http_get`, `filesystem.read`). Callers lacking required permissions receive `PermissionError`.
2. **Event Bus Delivery:** Event distribution via `ExtensionEventBus` filters events against extension permissions and subscribed event declarations (`subscribed_events`). Rate limiting limits dispatch to a maximum of 100 events/second to prevent event storms.
3. **Data Isolation:** Extensions cannot access raw database models, private identity keypairs (`data/identities/`), or unapproved memory namespaces.

---

## Sandbox Exception Isolation & Automatic Quarantine

When an extension function raises an unhandled exception during execution:
1. `ExtensionSandbox` catches the exception and increments `error_count`.
2. The exception details are recorded in `last_error`.
3. When `error_count >= max_error_threshold` (default: 3), the extension is automatically transitioned to `QUARANTINED` state.
4. Quarantined extensions are immediately blocked from executing further tools or receiving events.
