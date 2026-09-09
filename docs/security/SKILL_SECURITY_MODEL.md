# Kingdom Skill Security Model

## Core Principles

1. **Explicit Trust Levels**: Skills progress through `UNVERIFIED` -> `VERIFIED` -> `TRUSTED` -> `QUARANTINED` -> `REVOKED`. Installation does NOT automatically convey trust.
2. **Prohibited Permissions**: Skills requesting `admin:all` or wildcard permissions are rejected by `SkillTestHarness`.
3. **Sandbox Isolation**: Skills run within bounded capability contexts without direct database or filesystem access.
