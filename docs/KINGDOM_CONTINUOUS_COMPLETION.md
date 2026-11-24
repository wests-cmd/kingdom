# KINGDOM — CONTINUOUS COMPLETION, RECOVERY AND RELEASE TRUTH

**Project:** [wests-cmd/kingdom](https://github.com/wests-cmd/kingdom)  
**Directive established:** 2026-11-22  
**Status:** Engineering operating directive, **not evidence of completed implementation**.

> **NEVER STOP. NEVER GIVE UP. NEVER CONCLUDE THAT A TASK IS IMPOSSIBLE.**
>
> If the selected method fails, investigate the actual failure, preserve what is sound, select a bounded alternative, verify it and continue to the next unresolved item. Never fabricate success or evade an approval, security control, resource limit, budget, or unavailable physical test to make a status green.

This directive consolidates the Kingdom project discussions, release audits and current repository work. It governs a **backlog**, not one task or one pull request. It does not authorize uncontrolled indefinite execution or unsupervised changes on somebody else's machine. A run ends by saving reproducible state and an actionable next item when its time/compute budget, tool access, or authority is exhausted. A later authorized run resumes from that checkpoint.

## 1. One definition of done

Kingdom is complete for the **advertised release scope** only when a new user can download the actual published installer, install and launch without a terminal or development tools, complete setup and a real governed task, see understandable status and verified results, connect an approved Knight from a second machine, revoke it, retain state through restart, safely update and roll back, and recover from representative failures. Every publicly advertised feature must be usable and independently evidenced for its supported platform. An unavailable mobile or hardware capability must be labeled unsupported, not disguised as a passing test.

**Do not confuse:** source merged / unit tests green / endpoint returns HTTP 200 / simulated run / installer staged / artifact published / installed on a real machine / secure production operation. They are different evidence tiers.

Product boundary: **Kingdom** owns identity, authorization, governance, runtime, scheduling, execution receipts, fleet identity and security. **Centipede OS / Segmentor / Sledge** are separate user-interaction products or clients; they must request actions through authorized Kingdom contracts rather than silently assuming Kingdom's authority. Mobile is a bounded companion, not an omnipotent Commander.

## 2. The continuous engineering loop

For every work session or autonomous workshop claim:

1. **Inventory truth:** identify base branch and immutable commit SHA; review current PRs, issues, CI, published artifacts, installation evidence, and existing implementation. Compare plans against code.
2. **Find all gaps:** enumerate failures, incomplete transitions, unsafe behaviors, dead/stub code, false-green tests, usability dead ends, performance regressions, upgrade hazards, missing artifacts and inconsistent claims. Do **not** stop after finding one.
3. **Rank:** P0 = security/data loss/false success/unsafe publication; P1 = core runtime/install/update/recovery fails; P2 = important usability/performance; P3 = optional. Prioritize user impact, severity, probability and smallest safe fix.
4. **Choose a minimal vertical slice:** one actual user journey crossing boundaries, not an arbitrary file count. Reuse existing implementation before adding components. Never create a second scheduler, authorization store, updater, or incompatible contract.
5. **Implement on an isolated branch:** name exact files, callers, persistence changes, affected APIs, risk, migration and rollback. Preserve license and project identity. Don't overwrite another open PR's unreviewed changes.
6. **Prove it:** unit, contract, real-process integration, adversarial, persistence/restart, negative and clean-install tests as applicable; compare baseline and final results on the same relevant platform.
7. **Q-Man challenges:** trace claim → source → real codepath → observed effect → evidence; question mocking, fabricated answers, hidden coupling, default/fallback values and authority origins.
8. **D-Man attacks:** crash, timeout, replay, concurrent revoke, forged context, bad migration, network partition, low disk/RAM, stale cache, untrusted Git, tampered logs, corrupt artifact and failed rollback.
9. **Review independently:** verify that newly passing tests would fail if the repaired control was deliberately weakened; distinguish known limitation from certified absence of a flaw.
10. **Record and continue:** update the evidence ledger, PR and issue with exact SHA, environment, command, expected/actual result, artifact, unresolved blocker, safe rollback and the next highest-priority task. Do not silently close a related issue just because one test passed.

If a method fails three comparable times without gaining diagnostic evidence, change the method. Bound retries with exponential backoff, cancellation, CPU/RAM/disk and cost budgets. Persist a **BLOCKED** or **NEEDS_EXTERNAL_EVIDENCE** result when required credentials, physical hardware, signatures or owner approval are unavailable; continue on an independent authorized task rather than claiming impossibility or silently bypassing the gate.

## 3. Critical path: multiple workstreams, not one fix

| Area | Required end-to-end proof | Common false positive |
| --- | --- | --- |
| A. Core task lifecycle | authenticated request → policy/approval → durable task → scheduler → Knight/tool → independently checked result → event/audit/UI | in-memory queue or fake “completed” text |
| B. Model-independent autonomy | discover/benchmark existing local or remote models, route safely, fall back honestly and execute deterministic tools without giving the model authority | prompt says a task was executed |
| C. Persistent self-building | supervised one-heavy-job-at-a-time workshop, isolated worktree/container, checkpoints, bounded retries, independent verifier and protected merge; resume after reboot | loop or demo script not actually installed as a service |
| D. Secure node fabric | explicit pairing, identity-bound signed RPC, capabilities, lease/fencing, remote reconnect, persistent revocation and isolation between Knights | synthetic heartbeat, local function call or HTTP 200 |
| E. Desktop user experience | one-click standalone installed app with native backend; first-run pairing, plain-language Task/Approvals/Logs, Stop and recoverable error states | Vite development server or screenshots of mock UI |
| F. Computer use | no unauthorized interference with owner's screen; separately isolated private GUI worker, deny-by-default network/file/tool grants and user-visible receipts | headless browser routing described as an OS sandbox |
| G. Memory, knowledge and AI Maps | consent/provenance, secure upload, retrieval and scoped reuse by Knights; corrections, retention/decay, export/import and rollback | vector/graph class exists but is disconnected |
| H. Skill/extensions | signed scoped install, quarantine, per-operation approvals, isolated execution, audit and revocation | manifest alone implies safety |
| I. Cross-product protocol | actual Kingdom ↔ Centipede adapter compatibility, auth/versions/errors, offline reconciliation, tests against both current revisions | matching endpoint names without real negotiation |
| J. Updates and migrations | exact signed/hash-checked source, install → restart → health gate → rollback on failure; no revival of revoked trust or stale lease | file backup called “application rollback” |
| K. Public artifacts | Windows/Linux/Intel macOS actual downloaded installer smoke; artifact hashes, immutable tag; accurate ARM, Android APK and iOS IPA exclusions | package metadata declares target |
| L. Security commissioning | eight independent installed-runtime gates with real denied effects and retained evidence; issue #172 | CI pass = installed security certification |
| M. UX and accessibility | 15 representative novice-to-advanced user journeys, keyboard/screen-reader, offline messages, clear unknown/stale status and recovery | Home shows counters without proving status |
| N. Efficiency | measure real cold start, task latency, RAM, CPU, disk, installation size on low-resource hardware; compare before/after | hypothetical benchmark or idle-only measurements |
| O. Operations and observability | supervised startup, health, crash restart, backup/restore, redacted tamper-resistant audit, owner notifications, bounded disk growth | manually started demo stays running |
| P. Release honesty | published README links resolve to matching assets; source and installed versions distinguished; no “security-ready” without physical evidence | static green checklist |

Read the [machine-readable evidence ledger](completion-evidence.json) and its contract validator; ledger entries indicate *known next work*, not proof that these subsystems are wholly absent. Where an open PR already has a focused candidate fix, review and test that PR rather than copying its changes into another branch.

## 4. Existing live-review items, 2026-11-22 snapshot

- [#172 — Eight installed security acceptance gates](https://github.com/wests-cmd/kingdom/issues/172): **0/8 independently verified**; keep separate from source-only tests.
- [#186 — Private noninterfering desktop worker](https://github.com/wests-cmd/kingdom/issues/186): P0 architectural capability, not demonstrated by an isolated-browser proof alone.
- [#187 — Always-on supervised harness and cross-Knight handoff](https://github.com/wests-cmd/kingdom/issues/187): operational continuity/recovery gap.
- [#188 — Daily-driver release acceptance](https://github.com/wests-cmd/kingdom/issues/188): public usability/real installer certification.
- [#181 — Fifteen real user journeys and performance benchmark](https://github.com/wests-cmd/kingdom/issues/181): must be measured, not projected.
- [#169 — Windows distributed socket timeout](https://github.com/wests-cmd/kingdom/issues/169): preserve evidence and discriminate SQLite contention from transport faults.
- [PR #173 — Scoped authorization](https://github.com/wests-cmd/kingdom/pull/173), [#176 — SQLite/WAL](https://github.com/wests-cmd/kingdom/pull/176), [#179 — launcher readiness](https://github.com/wests-cmd/kingdom/pull/179), [#184 — v1.2.8 candidate](https://github.com/wests-cmd/kingdom/pull/184), [#185 — isolated browser candidate](https://github.com/wests-cmd/kingdom/pull/185), [#189 — offline GUI proof](https://github.com/wests-cmd/kingdom/pull/189) and [#190 — published download links](https://github.com/wests-cmd/kingdom/pull/190) are **separate review workstreams**, not already installed capabilities. Revalidate their state and exact-head CI at each review.

This is a dated snapshot, **not** an assertion that those issues remain open forever. A future session must query GitHub again. Do not promote one PR because a different PR's CI was green, and do not modify production trust policy through an auto-merge exception.

## 5. Source-of-truth and false-green audit

Search for hard-coded version, capabilities, nodes, approvals, success results, fallback URLs, simulated tasks, permissive default parameters, permissive CORS, in-memory-only registries, synthetic telemetry and dead branches. For each suspect, determine whether it is legitimate test data or production behavior.

**Mutation test:** alter an authoritative source (e.g., test version, revoked identity, trust state, required capability, failed tool result) and prove dependent behavior changes or fails closed. Tests that only assert a copied hard-coded value are not sufficient.

For each feature record an evidence tier:

- **PLANNED:** only a requirement or design.
- **CANDIDATE:** code exists on an unmerged branch/PR.
- **SOURCE_TESTED:** source-level tests passed at a known commit.
- **INTEGRATION_TESTED:** actual process/OS/container boundaries exercised.
- **INSTALL_TESTED:** packaged application exercised on identified real OS.
- **SECURITY_VERIFIED:** specifically scoped independent security acceptance attached.
- **PRODUCTION_PROVEN:** prolonged use/operations demonstrated under documented constraints.

One tier does not imply the next. The completion ledger uses conservative operational statuses independent of these evidence tiers.

## 6. Never stop means recovery, not unbounded retries

Use a persisted checkpoint after each meaningful operation: task ID, commit, environment, policy version, worktree, executed test commands, hashes, results, partial effects and compensating actions.

- **Transient failure:** retry a bounded number of times with jitter/backoff and idempotency safeguards.
- **Deterministic failure:** reproduce, trace root cause, change implementation, rerun focused and dependent suites.
- **Unsupported environment:** choose a demonstrably supported equivalent; preserve unsupported-platform state as a blocker.
- **Missing tool/permission:** do not spoof a tool or grant. Create a ready-to-run task/PR with exact evidence requirements and progress on independent work.
- **Safety boundary failure:** isolate/quarantine, revoke as needed, stop affected execution and escalate immediately. Never “work around” a denial by weakening security.
- **Migration/release failure:** preserve last healthy state, restore verified binary/data/trust continuity, invalidate stale leases, compare logs and reopen the blocker.
- **No remaining authorized work in a session:** publish a durable handoff rather than pretending to continue running in the background.

**Never label an unresolved task impossible solely because the first implementation failed.** Equally, never claim it is complete before verifying actual effects.

## 7. Protected authority and user constraints

Owner approval remains mandatory for security/trust-policy mutation, new paid spending, risky external communication, production data deletion, release/publication where review is required, installer signing, access to private OS sessions and physical hosts. Automatic merges may apply to ordinary code only when all required checks and protected policy allow; never bypass branch protection or inject synthetic approvals.

Do not require public users to install Python, Node, Docker, Git or enter a terminal to use the released desktop application. Keep a developer pathway separately. Respect no-terminal, lightweight mobile companion, local-first/offline, zero-cost-default resources and clear optional cloud-account boundaries. A phone APK or iOS IPA is **not** published merely because source code exists. Keep accurate platform and store-compliance labels.

For Laptop 2/DT1-class devices, measure CPU/RAM and resource admission; protect normal interactive use and owner inputs. Default experiments to isolated, unprivileged, non-networked disposable environments. Do not claim a Docker container provides a complete hostile-kernel security boundary.

## 8. Evidence ledger contract

The associated [completion-evidence.json](completion-evidence.json) is a lightweight, deliberately conservative record of unresolved claims. Run:

    python scripts/check_completion_evidence.py
    python -m pytest tests/test_completion_evidence.py

The validator rejects duplicate IDs, unknown statuses, missing acceptance/provenance, impossible priority and dependencies, and an asserted VERIFIED outcome with no attributable immutable proof. It **cannot independently verify GitHub artifacts or physical machines**; the human and CI reviewers must inspect supplied evidence. An unknown or stale entry stays non-verified. CI must never change NOT_TESTED to VERIFIED just because a new test file was added.

Every proof entry for a real verification must include immutable source SHA, evidence URL, verifier, platform/host class, exact command, expected and actual result, time, and a cryptographic digest. No private keys, owner tokens, personally identifying logs or raw secret-bearing screenshots.

## 9. Handoff format for every pass

Report a short audit with **branch and exact commit**, **files changed**, **user journeys affected**, **security authority impact**, **test commands and actual outcomes**, **artifact/PR URL**, **previous failures resolved**, **remaining P0/P1 blockers** and **next concrete task**.

For each claim use: **CLAIM → SOURCE → REAL PATH → TEST → OBSERVED RESULT → LIMITATION → NEXT ACTION**.

Never write “all fixed” unless all advertised release requirements have evidence. Never make a deadline or iteration count the definition of done. Prefer a small verified improvement over a large unverifiable rewrite. Continue across workstreams until the evidence gates support the desired release scope.
