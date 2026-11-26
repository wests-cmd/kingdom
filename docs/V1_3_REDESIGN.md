# Kingdom v1.3.0 controlled redesign

Base: merged v1.2.11. Do not replace the working main release while development is underway.

Definition of done: a single durable objective lifecycle, one existing identity and authorization authority, one scheduler with recoverable leases, one evidence-backed work projection across front doors, clear team/host distinctions, tested adapter capabilities, and independent verification. Keep Python/FastAPI, React/Electron, SQLite, signed RPC and the existing installer pipeline. Migrate incrementally; no parallel scheduler or new authority service.

1. First vertical slice: permanent model matrix and precise model evidence.
2. Establish a read-only canonical work projection, then migrate requests/missions/agent/harness dispatch through a shared admission contract using existing repositories.
3. Bind consequential effects to durable authorization and fencing; require adversarial tests and explicit owner review for trust policy changes.
4. Consolidate the desktop into Conversation, Command Center, Missions, Knowledge Vault, Connections, Approvals and Settings. Keep graph coordinates separate from authority.
5. Resource-aware scheduler, recovery and failure receipts across Knight computers; one heavy job by default for constrained hosts.
6. Unified model/MCP/harness adapter capabilities; preserve free/local defaults, tool grants and explicit external provider use.
7. Isolated self-improvement loop with independent tests, reviewed promotion, rollback that preserves security state, verified memory and skills.
8. Commission physical devices, signed installers and mobile packages where credentials/platforms permit. Issue #172 is not closed by unit tests.

Every slice must retain existing regressions and add its own tests. The model matrix is permanent from v1.3.0 onward; report real small, medium and large evidence separately from fixture tests. Source correctness is not installed production certification.
