# Kingdom historical branch retirement — final review (2026-11-20)

The original 31 reviewed branches were archived and retired successfully in [run 44782217907](https://github.com/wests-cmd/kingdom/actions/runs/44782217907). Every original SHA is recorded in [the manifest](branch_retirement_manifest.json) and preserved under remote tags `kingdom-history/2026-11-19/<branch-name>`.

The remaining four branches were independently inspected and **explicitly rejected as legacy implementations** (not falsely described as merged). The decision, comparison, selected regression and constraints are recorded in [the four-branch review](FOUR_BRANCH_REVIEW_2026-11-20.md).

**Outcomes:** 5 original branches had work integrated, 26 were superseded by later code, and 4 were archived-not-adopted. Only `main` and `integration/kingdom-cohesion-20261119` are keeper branches once the final four refs are retired. A branch can be deleted without losing its source under the verified tag. A deleted branch is **not** evidence that its old features operate in Kingdom.

The open external-monitor draft PR #131 was rejected because its actual separately isolated Linux signer had not been commissioned; do not auto-merge that policy-changing integration.

## Retirement controls

- Always check branch head == manifest SHA and tag SHA == manifest SHA.
- Prevent deletion when a PR is open against that head.
- Preserve both keeper branches; use force-with-lease for deletions.
- The manual retirement workflow is the normal choice, requiring `ARCHIVE_AND_RETIRE_35`; a one-time verified cleanup workflow is removed after it completes.
- CI, native validation, physical 2/5-node rehearsal and update rollback are separate release gates—not proven by branch cleanup.

## Complete historical inventory

| Branch | Disposition | Reason |
| --- | --- | --- |
| `bolt/audit-log-history-speedup-16176806299477506921` | `integrated` | AuditLogger.history now uses bounded reverse iteration, with append/eviction locking and tests. |
| `bolt/memory-search-token-cache-8691068860340529059` | `superseded` | Current memory service has token cache and more recent query behavior; historical one-file optimization is not authoritative. |
| `bolt/optimize-learning-collector-get-outcomes-12740401110657446076` | `superseded` | Current learning collector has bounded retrieval already; old get_outcomes optimization not independently adopted. |
| `bolt-stream-consultation-queries-2243824996762498214` | `integrated` | Bounded SQL consultation streaming and tests were ported in PR #165. |
| `codex/autonomy-security-next-20261102` | `superseded` | Current gap register endpoints already enforce owner dependency and strictly typed evidence; clean duplicate imports separately. |
| `codex/centipede-compatibility` | `superseded` | Current Centipede compatibility, release process and installer contract supersede this older branch. |
| `codex/harness-readiness-repair-20261101` | `superseded` | Newer read-only adapter discovery API/UI is in main; old ACP implementation not copied wholesale. |
| `codex/harness-repair-input-20261102` | `superseded` | Current adapter implementation keeps unverified binaries from being advertised as connected or authorized. |
| `codex/monitor-execution-guard-20261023` | `archived_not_adopted` | ARCHIVED, NOT MERGED: Linux-only external Ed25519 signer is a genuine separate security model, but no demonstrated OS-principal isolation or installed fail-closed fleet acceptance. Do not splice a new signer into current ZeroTrust; preserve source/tag for a future separately threat-modeled project. |
| `codex/opt-in-parallel-pan-paths-20261024` | `superseded` | Main has a newer opt-in signed LAN/Bluetooth PAN probe with identity and route checks; draft PR #133 remains open. |
| `codex/preview-release-status` | `superseded` | Main README and status document describe later published v1.2.4; older preview status is obsolete. |
| `codex-adapter-observation-repair-20261103-12474211212681984112` | `integrated` | A read-only tested adapter inventory and model discovery were integrated into the native desktop via PR #165. |
| `docs/downloads-and-discord` | `superseded` | README now includes verified v1.2.4 downloads and Discord/community links. |
| `docs/v112-downloads` | `superseded` | v1.1.2 download note is obsolete; main publishes v1.2.4 packages. |
| `feat/autonomous-harness-foundation-17802645864919866654` | `archived_not_adopted` | ARCHIVED, NOT MERGED: experimental IsolatedBuildRunner does not apply candidate changes before running tests; its claimed repair loop can pass without testing the patch. Retain modern existing proposal guards. Selectively port the owner's Gap Register denial regression tests, not the fake executor. |
| `feat-native-jules-handoff-adapter-9784710610709854012` | `superseded` | Main Jules adapter is much larger and includes owner gates, encrypted secret handling, deterministic job lifecycle and review. |
| `feature/agentscope-additions` | `superseded` | Current accessibility/recovery/checkpoint mechanisms and desktop UX supersede early AgentScope additions. |
| `feature/durable-workflow-checkpoints` | `superseded` | Current workflow checkpoint and recovery implementations supersede earlier prototype. |
| `feature/inplace-desktop-updates` | `superseded` | Current Windows desktop update and signed artifact protocol supersede historical v1.2.1 work. |
| `feature/mission-workspace` | `superseded` | Main mission task API, file upload, approvals and workspace are newer and broadly tested. |
| `feature/royal-appearance-settings` | `superseded` | Current appearance settings, light/dark options and first-run desktop settings supersede old styling branch. |
| `feature/verified-automation-handover` | `superseded` | Main includes audited automation handover routes, guarded policy and supervision. |
| `fix/audit-log-sanitization-8026888189466175010` | `superseded` | Current sanitization and bounded audit logging cover this older patch; PR #165 adds thread-safety. |
| `fix/device-pairing-user-flows` | `superseded` | Main has current remote pairing flow, fingerprint approvals, node revocation and tests. |
| `fix/docker-worker-enrollment` | `superseded` | Main Docker enrollment and cluster documentation supersede the initial worker installer. |
| `fix/final-control-clarity` | `superseded` | Main UI and Nodes/Cluster permissions separate trust and task authority; old style-only changes obsolete. |
| `fix/independent-installations` | `superseded` | Main identity handling and first-time setup separate installed owner from remote pairing. |
| `fix/node-token-timing-validation-4845865787450809576` | `integrated` | Constant-time token compare, collision-safe rotation and malformed token rejection ported with tests in PR #165. |
| `jules-12217898583924398317-1da231a0` | `archived_not_adopted` | ARCHIVED, NOT MERGED: old general API catalog auto-fetches and follows redirects to untrusted provider URLs; provider verification does blind GET with redirects, risking SSRF. Static metadata inferred from auth alone cannot prove an API free or functional. Keep existing truthful read-only discovery; future catalog needs design and new implementation. |
| `jules-9044776383071301607-06615c47` | `superseded` | No additional changed files versus main; historical commit reachable only through archive tag. |
| `jules-external-oracle-harness-4034832206850530088` | `archived_not_adopted` | SUPERSEDED: current main already has scripts/jules-external-oracle.py and tests, stronger pinned-instance/source/isolation checks and verified test fixtures. Never overwrite it with older implementation. Harden current probe transport to keep disposable auth header out of process argv. |
| `review/readiness-progress-20261103` | `superseded` | Read-only adapter discovery revised after this review branch; latest main code is source of truth. |
| `sentinel/constant-time-node-auth-18283649182827028197` | `integrated` | Constant-time node authentication and stronger token validation covered by main regression tests. |
| `sentinel/fix-credential-broker-sanitization-8341564342343024733` | `superseded` | Main credential broker and recent dependency pins supersede old token redaction and lockfile churn. |
| `sentinel/prompt-firewall-custom-exception-5861370810917762694` | `superseded` | Current prompt firewall includes dedicated rejection exceptions and test coverage; old patch unnecessary. |
