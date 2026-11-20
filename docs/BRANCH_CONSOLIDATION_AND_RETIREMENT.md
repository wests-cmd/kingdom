# Kingdom historical branches: evidence and safe retirement

**Updated 2026-11-20 after merged PRs [#165](https://github.com/wests-cmd/kingdom/pull/165) and [#166](https://github.com/wests-cmd/kingdom/pull/166).** This is a source-branch audit and retirement record, not an installed-fleet acceptance certificate.

## Completed cleanup — 2026-11-20

- **31 historical branches deleted** through the audited workflow [run 44782217907](https://github.com/wests-cmd/kingdom/actions/runs/44782217907), with no deletion errors.
- **35/35 exact historic commit heads are preserved** by verified remote tags under `kingdom-history/2026-11-19/` (including the four held branches).
- **4 branches retained** for unfinished distinct features: security monitor, self-build harness, provider catalog and standalone Jules oracle.
- **Only six branches remain**: `main`, `integration/kingdom-cohesion-20261119`, and those four held branches.
- Five superseded historical pull requests (#123, #133, #149, #163, #164) were closed with review explanations. Draft #131 (external monitor) remains open.
- The special one-time deletion workflow was removed after success. Normal workflow pushes are archive-only; future deletion remains manually authorized.

**Do not mistake retention under archive tags for implemented feature parity.** No full-tree mass merges were performed. Latest verified production release remains distinct from updated main source.

## Decision

**The 31 reviewed branches have been retired; do not delete the four held branches yet.** Main includes the selected runtime/security fixes but it does not contain every historical experiment. Each branch has a pinned SHA and explicit disposition in [the machine-checked manifest](branch_retirement_manifest.json). This preserves a complete, reviewable map instead of assuming that a clean merge means functional parity.

| Code disposition | Count | Safe to delete after archive and PR closure? |
| --- | ---: | --- |
| Integrated in main | 5 | Yes, subject to checks |
| Superseded by newer main implementation | 26 | Yes, subject to checks |
| Needs distinct engineering review | 4 | **No** |

## Four historical features explicitly NOT covered

- **`codex/monitor-execution-guard-20261023`** (pinned `aee1296f9787`): Linux external signer and durable monitor are NOT on main; separate UID, on-host integrity and live fail-closed tests required before adoption. Open draft PR #131.
- **`feat/autonomous-harness-foundation-17802645864919866654`** (pinned `980772d68965`): Experimental IsolatedBuildRunner and state machine are not on main; old runner does not actually apply proposed files and must not be represented as executable self-repair.
- **`jules-12217898583924398317-1da231a0`** (pinned `f60585244e67`): Profile/API catalog with database, provider sync and frontend is missing from main. Model profiles exist but are NOT equivalent; review external source availability and SSRF/authorization boundaries.
- **`jules-external-oracle-harness-4034832206850530088`** (pinned `df15fe1fba09`): Standalone Jules external-oracle harness CLI is absent from main; existing native Jules adapter is not equivalent to the offline verification CLI.

The catalog branch implements a general **API provider catalog**, which is different from current configured **model profiles**. The monitor branch implements a separate Linux UID and Ed25519 receipt process, which is different from Kingdom's current in-process audit log. The Jules external-oracle CLI and the isolated self-build runner are not proof of equivalent current functionality either.

**Do not cherry-pick these entire branches.** The monitor requires multi-process identity/isolation tests, key protection, fail-closed operation evidence, and Windows/macOS opt-in semantics; the catalog needs provider URL validation, safe verification and owner-only lifecycle; the old builder must actually apply isolated file edits and pass immutable tests; and the old Jules script needs comparison with the current vetted Jules adapter.

## Outstanding pull request

Only the [draft external-monitor PR #131](https://github.com/wests-cmd/kingdom/pull/131) remains open on a historical branch. It has not been merged because separate-host identity isolation and crash/fail-closed acceptance remain unproven. Retire it only after an implementation review, tests, and archive verification. [Issue #167](https://github.com/wests-cmd/kingdom/issues/167) tracks the remaining four feature areas.

## Exact per-branch disposition

| Historical branch | Classification | Main decision |
| --- | --- | --- |
| `bolt/audit-log-history-speedup-16176806299477506921` | integrated | AuditLogger.history now uses bounded reverse iteration, with append/eviction locking and tests. |
| `bolt/memory-search-token-cache-8691068860340529059` | superseded | Current memory service has token cache and more recent query behavior; historical one-file optimization is not authoritative. |
| `bolt/optimize-learning-collector-get-outcomes-12740401110657446076` | superseded | Current learning collector has bounded retrieval already; old get_outcomes optimization not independently adopted. |
| `bolt-stream-consultation-queries-2243824996762498214` | integrated | Bounded SQL consultation streaming and tests were ported in PR #165. |
| `codex/autonomy-security-next-20261102` | superseded | Current gap register endpoints already enforce owner dependency and strictly typed evidence; clean duplicate imports separately. |
| `codex/centipede-compatibility` | superseded | Current Centipede compatibility, release process and installer contract supersede this older branch. |
| `codex/harness-readiness-repair-20261101` | superseded | Newer read-only adapter discovery API/UI is in main; old ACP implementation not copied wholesale. |
| `codex/harness-repair-input-20261102` | superseded | Current adapter implementation keeps unverified binaries from being advertised as connected or authorized. |
| `codex/monitor-execution-guard-20261023` | review_required | Linux external signer and durable monitor are NOT on main; separate UID, on-host integrity and live fail-closed tests required before adoption. Open draft PR #131. |
| `codex/opt-in-parallel-pan-paths-20261024` | superseded | Main has a newer opt-in signed LAN/Bluetooth PAN probe with identity and route checks; draft PR #133 remains open. |
| `codex/preview-release-status` | superseded | Main README and status document describe later published v1.2.4; older preview status is obsolete. |
| `codex-adapter-observation-repair-20261103-12474211212681984112` | integrated | A read-only tested adapter inventory and model discovery were integrated into the native desktop via PR #165. |
| `docs/downloads-and-discord` | superseded | README now includes verified v1.2.4 downloads and Discord/community links. |
| `docs/v112-downloads` | superseded | v1.1.2 download note is obsolete; main publishes v1.2.4 packages. |
| `feat/autonomous-harness-foundation-17802645864919866654` | review_required | Experimental IsolatedBuildRunner and state machine are not on main; old runner does not actually apply proposed files and must not be represented as executable self-repair. |
| `feat-native-jules-handoff-adapter-9784710610709854012` | superseded | Main Jules adapter is much larger and includes owner gates, encrypted secret handling, deterministic job lifecycle and review. |
| `feature/agentscope-additions` | superseded | Current accessibility/recovery/checkpoint mechanisms and desktop UX supersede early AgentScope additions. |
| `feature/durable-workflow-checkpoints` | superseded | Current workflow checkpoint and recovery implementations supersede earlier prototype. |
| `feature/inplace-desktop-updates` | superseded | Current Windows desktop update and signed artifact protocol supersede historical v1.2.1 work. |
| `feature/mission-workspace` | superseded | Main mission task API, file upload, approvals and workspace are newer and broadly tested. |
| `feature/royal-appearance-settings` | superseded | Current appearance settings, light/dark options and first-run desktop settings supersede old styling branch. |
| `feature/verified-automation-handover` | superseded | Main includes audited automation handover routes, guarded policy and supervision. |
| `fix/audit-log-sanitization-8026888189466175010` | superseded | Current sanitization and bounded audit logging cover this older patch; PR #165 adds thread-safety. |
| `fix/device-pairing-user-flows` | superseded | Main has current remote pairing flow, fingerprint approvals, node revocation and tests. |
| `fix/docker-worker-enrollment` | superseded | Main Docker enrollment and cluster documentation supersede the initial worker installer. |
| `fix/final-control-clarity` | superseded | Main UI and Nodes/Cluster permissions separate trust and task authority; old style-only changes obsolete. |
| `fix/independent-installations` | superseded | Main identity handling and first-time setup separate installed owner from remote pairing. |
| `fix/node-token-timing-validation-4845865787450809576` | integrated | Constant-time token compare, collision-safe rotation and malformed token rejection ported with tests in PR #165. |
| `jules-12217898583924398317-1da231a0` | review_required | Profile/API catalog with database, provider sync and frontend is missing from main. Model profiles exist but are NOT equivalent; review external source availability and SSRF/authorization boundaries. |
| `jules-9044776383071301607-06615c47` | superseded | No additional changed files versus main; historical commit reachable only through archive tag. |
| `jules-external-oracle-harness-4034832206850530088` | review_required | Standalone Jules external-oracle harness CLI is absent from main; existing native Jules adapter is not equivalent to the offline verification CLI. |
| `review/readiness-progress-20261103` | superseded | Read-only adapter discovery revised after this review branch; latest main code is source of truth. |
| `sentinel/constant-time-node-auth-18283649182827028197` | integrated | Constant-time node authentication and stronger token validation covered by main regression tests. |
| `sentinel/fix-credential-broker-sanitization-8341564342343024733` | superseded | Main credential broker and recent dependency pins supersede old token redaction and lockfile churn. |
| `sentinel/prompt-firewall-custom-exception-5861370810917762694` | superseded | Current prompt firewall includes dedicated rejection exceptions and test coverage; old patch unnecessary. |

## Remaining retirement process

The first 31 branches are already deleted and their remote archive tags have been checked against the pinned manifest. Keep the four held branches until each has either been adapted and tested in today's architecture or explicitly rejected with evidence.

1. For each held branch, finish the acceptance criteria in [Issue #167](https://github.com/wests-cmd/kingdom/issues/167). Never directly replace main's security, runtime or model authorization subsystems with historic trees.
2. Run the manual **audit** workflow; it checks the pinned expected SHA against live branch refs and checks for open pull requests.
3. Update `docs/branch_retirement_manifest.json` only when evidence warrants a new reviewed disposition.
4. Once all matching tags still exist and open PRs are resolved, manually run `archive-and-delete` with `ARCHIVE_AND_RETIRE_35`. The script skips everything unresolved and uses force-with-lease.
5. Confirm the expected final two branches: `main` and `integration/kingdom-cohesion-20261119`.

## Quality gates

- Latest branch CI must pass, including owner-only APIs and no bypass of policy.
- Verify real native installers and rollback on supported platforms before release.
- Test multiple physical nodes and interruption/recovery before treating distributed autonomy as accepted.
- A history tag is recoverable source, **not** a working feature, deployment approval or warranty.

This review did not delete branches, close PRs, publish a release, or claim physical-device verification.
