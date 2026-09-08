# Identity & Authorization Security Model

## Non-Negotiable Security Principles

1. **Kingdom Authority Rule:** Models, planners, and intelligence modules never possess execution authority. Kingdom backend code is the sole security boundary.
2. **Deterministic Authorization:** Authorization requests evaluate identity, capabilities, risk, data scope, and context deterministically. Global `if user == admin` checks are prohibited.
3. **Immutable Plan Parameter Hashing:** Approvals are cryptographically bound to plan parameters (`PlanDriftEngine`). Arguments modified post-approval raise `PermissionError`.
4. **Independent State Verification:** Operations are independently verified. Unverifiable actions output `UNKNOWN` state instead of defaulting to `SUCCESS`.
5. **Data Scope Isolation:** Restricted data scopes (e.g. `finance`, `personal`) require `TRUSTED` identity status.
