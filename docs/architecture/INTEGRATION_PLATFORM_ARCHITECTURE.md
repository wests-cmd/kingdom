# Kingdom Integration Platform Architecture

## Canonical Execution Pipeline
Every external integration in Kingdom follows a strictly bounded execution chain:

```
Integration Manifest
       ↓
Provider Abstraction
       ↓
Tool Schema & Registration
       ↓
Capability & Permission Boundary
       ↓
Kingdom Governance & Authorization
       ↓
Workflow Engine (L0–L4 Autonomy)
       ↓
Knight Execution
       ↓
Verification Engine
```

## Layer Separation Principles
1. **Core Runtime**: Owns state, cryptographic identity, zero-trust authorization, governance approval, and audit logs.
2. **Integration / Provider**: Translates third-party API contracts into Kingdom standard input/output models. Never executes directly without authorization.
3. **Tool**: A bounded, typed function definition (`tool@version`) declaring required capabilities and permissions.
4. **Skill**: Reusable workflow patterns that orchestrate tools to perform domain-specific objectives.
5. **Knight**: The execution worker bound by granted capabilities and fencing lease tokens.
