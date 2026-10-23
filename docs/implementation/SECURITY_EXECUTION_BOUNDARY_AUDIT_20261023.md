# Security execution boundary audit — 2026-10-23

Scope: Kingdom source, based on commit 783a0f8. This audit verifies implementation; the supplied research brief is an input, not evidence that its cited papers or percentages are correct. No live grants, policies, fleet installations, firmware or identities changed.

## Reproduced and fixed

`DOOMSDAY_APPROVAL_SCOPE_ESCALATION_remote_node_substitution` failed before this patch: after a human approved a task offered to node A, the real runtime dispatcher spent that same approval on node B. The original approval engine already bound actor, capability, operation, task identifier, prompt and metadata, with expiration and durable atomic single consumption. The missing binding was the dispatcher-selected execution destination, which is not necessarily task metadata.

The runtime now adds backend-authored placement, actual node, dispatch capability, policy level and persisted policy revision to the exact approval parameters. Neither model text nor task metadata can overwrite that context. Policy revisions come from the persisted UUID (existing legacy policies use their stored update timestamp until their next owner change); old authority endpoints without revision retain level binding but cannot prove same-level revision changes until upgraded. Local and remote placement remain distinct even if a remote node is literally named local. Rejected explicit approval use produces a separate DENIED audit event before a new approval request. No capabilities are granted by approval. Level 5 standing owner authorization remains unchanged.

Tests exercise real authorization/dispatch, not an agent explanation: substituted destination, task, prompt, argv, resource, actor, dispatch capability and policy revision; durable concurrent single-use spending from four restarted approval engines; expiration. Existing valid local/remote approval flows still pass.

## Verified protections and remaining work

| Area | Existing boundary inspected | Remaining work / limit |
| --- | --- | --- |
| Approval | SQLite BEGIN IMMEDIATE decision/consume; exact actor/capability/operation/JSON parameters; expiration; one use; owner-authenticated approval API | New target/policy binding added here. The task-level grant is not a universal per-system-call sandbox; process descriptors and OS grants still define actual execution. |
| Monitoring | Audit logger writes to disk before returning; failures propagate rather than treating execution as audited; authorization denies out-of-scope use | Logger runs in the Kingdom process and its user account. This is NOT an independently protected OS supervisor. A granted arbitrary process running as the same account may modify files; enforcement requires separately owned monitor/policy files, restricted worker identity and a supervisor liveness gate. A Python flag or agent promise cannot establish that boundary. |
| Stateful execution | Task transition state machine; mission approval/revisions; plan drift actor/tool/resource/parameter binding; work programme section integration gates | These are scoped workflows, not a universal READ/PREPARE/APPROVE/WRITE/VERIFY security automaton. Complete every executor integration before claiming universal coverage. |
| Identity/RPC | Signed canonical payload includes target; intended destination checked; sender current restricted states rejected; bounded timestamp skew; durable duplicate ledger; fail closed when ledger unavailable | Physical-node current authorization/revocation checks remain distinct from cryptographic validity. This source audit is not a fresh physical reconnection/rotation proof. |
| Recovery/fencing | SQLite authoritative latest task lease; exact integer fencing token; destination and expiry/revocation checked; interrupted side effects enter RECOVERY_REQUIRED while known idempotent analysis may requeue | Worker-level physical side-effect fencing and global leader election are not established by this audit. No universal bounded aggregate pending queue was found; define admission/backpressure budgets before outage stress claims. |

## Next acceptance gates

1. Integrate target-bound approval regression in release candidate, run full backend suite.
2. Add independently owned monitor supervisor and restricted process identity; prove worker cannot alter its configuration or suppress required audit and high-risk execution denies on supervisor loss.
3. Exercise stateful policy stages through every real side-effect executor; do not merely unit-test an unused engine.
4. Physical multi-process identity rotation/revocation and partition tests with pinned identities and current authorization at execution.
5. Bounded per-worker/global admission and outage memory stress; no automatic replay of unknown side effects.

The broader five DOOMSDAY scenarios are NOT all declared passed. A successful unit suite does not prove prompt-injection resistance of an actual model or OS isolation.

