# Kingdom v1.3.0 controlled redesign

Base: merged v1.2.11. Do not replace the working main release while development is underway.

Definition of done: a single durable objective lifecycle, one existing identity and authorization authority, one scheduler with recoverable leases, one evidence-backed work projection across front doors, clear team/host distinctions, tested adapter capabilities, and independent verification. Keep Python/FastAPI, React/Electron, SQLite, signed RPC and the existing installer pipeline. Migrate incrementally; no parallel scheduler or new authority service.

1. First vertical slice: permanent model matrix and precise model evidence.
2. Read-only canonical work projection implemented in the development candidate (CI pending; see [work projection](UNIFIED_WORK_PROJECTION.md)); then migrate requests/missions/agent/harness dispatch through a shared admission contract using existing repositories.
3. Bind consequential effects to durable authorization and fencing; require adversarial tests and explicit owner review for trust policy changes.
4. Consolidate the desktop into Conversation, Command Center, Missions, Knowledge Vault, Connections, Approvals and Settings. Keep graph coordinates separate from authority.
5. Resource-aware scheduler, recovery and failure receipts across Knight computers; one heavy job by default for constrained hosts.
6. Unified model/MCP/harness adapter capabilities; preserve free/local defaults, tool grants and explicit external provider use.
7. Isolated self-improvement loop with independent tests, reviewed promotion, rollback that preserves security state, verified memory and skills.
8. Commission physical devices, signed installers and mobile packages where credentials/platforms permit. Issue #172 is not closed by unit tests.

Every slice must retain existing regressions and add its own tests. The model matrix is permanent from v1.3.0 onward; report real small, medium and large evidence separately from fixture tests. Source correctness is not installed production certification.

### Conversation admission consolidation (incremental)

Commander drafts, delegated tasks, harness tasks and agent sessions now share a durable compare-and-swap admission checkpoint in RequestService. A stale running snapshot cannot claim a second admission; an existing intent without a linked child is held for review rather than replayed. The checkpoint confers no permission. Existing child services remain responsible for authorization and execution. Direct non-conversation entry points and independent physical/model acceptance remain outside this slice. Regression tests cover all four routes, competing claims, cancellation and retained children; CI evidence is required before accepting the slice.

### Durable task admission across dispatchers

All new tasks use an insert-only repository operation instead of a creation-time upsert. The deterministic mission/agent step identifier now resolves collisions from persisted state, even when a second dispatcher has a stale cache. A conflicting prompt or reviewed operation/parent binding is rejected; existing terminal results, cancellation, lease and version data are never replaced by task creation. The scheduler and existing authorization service are unchanged. Regression coverage uses independent TaskManager instances sharing a real temporary WAL database. This does not yet provide idempotency keys for all external HTTP entry points or prove multi-host failover.

Admission exception recovery now uses the same read-only child matching as startup recovery. An exception after a child is committed but before its parent linkage is saved is held for explicit review, and older failed requests with a durable submission marker and no child linkage are reconciled on restart. No new job, authorization or completion receipt is created by recovery. Added regression cases for a post-commit submission error and a retained legacy failed checkpoint.
