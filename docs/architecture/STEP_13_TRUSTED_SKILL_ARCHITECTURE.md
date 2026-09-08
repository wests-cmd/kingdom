# Step 13 — Trusted Skill Architecture

## Overview

Kingdom v40.2 enforces a canonical, manifest-driven trust model for AI skills. A skill cannot grant itself permissions or capabilities.

```text
CANONICAL SKILL MANIFEST (CanonicalSkillManifest)
 ↓
MANIFEST VALIDATOR (Prohibited Permission Check & Schema Validation)
 ↓
SKILL TRUST REGISTRY (SkillTrustRegistry)
 [ UNVERIFIED -> VERIFIED -> TRUSTED -> QUARANTINED -> REVOKED ]
 ↓
CAPABILITY BOUNDARY CHECK (verify_execution_authority)
 ↓
KINGDOM EXECUTION BOUNDARY
 ↓
OUTPUT DATA ISOLATION (Outputs remain untrusted DATA)
```

---

## Canonical Skill Trust Levels

1. **`UNVERIFIED`**: Newly registered skill; unverified publisher.
2. **`VERIFIED`**: Publisher signature and manifest validated.
3. **`TRUSTED`**: Passed sandbox evaluation and security review.
4. **`QUARANTINED`**: Isolated due to execution anomalies or error thresholds.
5. **`REVOKED`**: Permanently revoked due to security compromise.

---

## Capability Boundaries & Output Security

- **Declared Capabilities:** A skill must explicitly declare required capabilities in its manifest. Requests for undeclared capabilities raise `PermissionError`.
- **Prohibited Permissions:** Manifests requesting prohibited kernel permissions (`kernel.bypass_security`, `system.disable_audit`) are rejected during registration.
- **Output Isolation:** Skill outputs remain untrusted `DATA` and cannot automatically become system instructions, policies, or capability grants.
