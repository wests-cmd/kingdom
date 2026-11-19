# Kingdom integration and branch-cohesion review — 2026-11-19

## Baseline and scope

This branch starts at `main` commit `2c6f2b555094a74ea87eaedeedbd81f8c4ce804c` (1,012 tracked source files at review). The older uploaded ZIP has only 178 archive entries and is **not** a current implementation baseline. Do not merge it over the live code.

Review method: inspect each GitHub branch against `main`, prefer only bounded, inspectable deltas, then prove live task paths separately. A branch being ahead or a module existing does **not** establish release readiness.

## Reapplied fixes from branch reviews

- `bolt-stream-consultation-queries-2243824996762498214`: stream consultation list/claim reads instead of eagerly deserializing every stored JSON row; preserve ordering, limits and SQL transaction.
- `fix/node-token-timing-validation-4845865787450809576`: reject malformed token inputs and scan registered tokens using `secrets.compare_digest` rather than direct indexed lookup. This is not a formal constant-time guarantee across arbitrary lengths, runtimes or concurrency.
- Additional mainline defect: re-registering an identity previously left its old credential authenticating; rotate and invalidate the old mapping, block explicit reuse across distinct identities, and synchronize mutation/authentication.
- Additional mainline defect: `KnightDaemon` previously defaulted to `KG-MASTER-01` when Commander identity discovery failed. Remote signing/pairing now fails closed instead.

These changes are narrowly scoped. They do **not** certify a full distributed release. They have added regression tests but require execution under CI and on actual installed peer devices before promotion.

## Branch inventory and decision

| Branch/group | Reviewed divergence from main | Decision |
| --- | --- | --- |
| `bolt-stream-consultation-queries-2243824996762498214` | 1 ahead / 0 behind | Selectively reapplied bounded query optimization |
| `fix/node-token-timing-validation-4845865787450809576` | 1 ahead / 0 behind | Selectively reapplied auth validation |
| `feat/autonomous-harness-foundation-17802645864919866654` | 3 ahead / 44 behind | Keep; reconcile self-build guard/gap-register tests individually |
| `codex/autonomy-security-next-20261102` | 2 ahead / 29 behind | Keep; examine gap-register owner boundary and preserve newer main |
| `codex/harness-readiness-repair-20261101` | 1 ahead / 45 behind | Keep; ACP adapters require a live integration check |
| `feature/durable-workflow-checkpoints` | 8 ahead / 296 behind | Do not merge wholesale; evaluate recovery/checkpoint code against current engine |
| `feature/mission-workspace` | 7 ahead / 283 behind | Do not merge wholesale; current mission paths have evolved |
| `feature/inplace-desktop-updates` | 10 ahead / 281 behind | Do not merge wholesale; installed-update verification and rollback required |
| `fix/device-pairing-user-flows` | 8 ahead / 315 behind | Do not merge wholesale; identity and pairing regression risk |
| `fix/docker-worker-enrollment` | 1 ahead / 297 behind | Evaluate pairing helper against today's Docker Compose |
| `feature/verified-automation-handover` | 2 ahead / 284 behind | Verify authority and background job lifecycle before selective reuse |
| `codex-adapter-observation-repair-20261103-12474211212681984112` | 1 ahead / 6 behind | Closest ACP adapter candidate; rebase and run adapter tests |
| `bolt/audit-log-history-speedup-16176806299477506921` | 2 ahead / 279 behind | Review sanitized logs and pagination before selective reuse |
| `bolt/memory-search-token-cache-8691068860340529059` | 1 ahead / 200 behind | Benchmark against current memory service |
| `sentinel/constant-time-node-auth-18283649182827028197` | 3 ahead / 54 behind | Superseded in part by narrower token hardening; review other changes separately |
| Other older docs / UI / Jules / harness / cluster branches | Often hundreds of commits behind `main` | Retain for reference, no unreviewed mass merge |

## The machine: mandatory authoritative flow

```text
Desktop / Mobile / Centipede client
  -> authenticated owner or approved node identity
  -> request validation and scoped capability authorization
  -> durable task + idempotency key
  -> scheduler and lease/fencing authority
  -> governed local executor or signed remote Knight RPC
  -> result verification (never synthetic success)
  -> durable outcome, audit, event, API and UI
  -> bounded improvement proposal, separately gated by policy
```

A unit test or route returning HTTP 200 does not prove this flow. CI needs a two-process end-to-end test, remote lease rejection, restart/reconnection, real installed desktop and Docker smoke tests. `main` already has many dedicated modules; do not create a second authority implementation.

## Release blockers requiring separate proof

1. Trace a real task with a stable ID through authorization, persistence, lease, execution, verification, result and audit, across a real network process boundary.
2. Prove revoked and re-enrolled nodes cannot reuse stale tokens, messages, claims or task fences after restart.
3. Test desktop install/update/rollback on actual Windows/Linux and signed/notarized platforms separately; source code is not an installer.
4. Show one central runtime supervisor owns each background runner, ensures clean shutdown and exposes actual degraded readiness.
5. Prove portable memory/AI Map import remains untrusted until independently approved and never grants tool authority.
6. Test low-memory (<4 GiB) CPU-only settings with task concurrency limits, bounded event/storage growth and disk-pressure recovery.
7. Run all unit, API, integration, distributed, security, frontend, Docker and packaging checks on this exact commit and record exact outcomes.

**Status:** integration repair branch / not certified as one-click production release. No live test results are claimed in this review.
