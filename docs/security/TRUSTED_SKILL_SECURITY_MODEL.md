# Trusted Skill Security Model

## Non-Negotiable Security Principles

1. **Manifest Validation:** All skills require canonical `CanonicalSkillManifest` declarations specifying capabilities and permissions.
2. **Prohibited Skill Permissions:** Prohibited permissions (`kernel.bypass_security`, `system.disable_audit`, `governance.auto_approve`, `root.escalate`) are rejected at registration.
3. **Capability Boundary Enforcement:** Attempting to execute capabilities not declared in the skill manifest raises `PermissionError`.
4. **Authoritative Revocation:** Revoked skills (`REVOKED` state) fail closed instantly across all execution paths.
5. **Output Data Containment:** Skill outputs remain untrusted data payloads. Model inferences or skill outputs cannot grant permissions or alter security policy.
