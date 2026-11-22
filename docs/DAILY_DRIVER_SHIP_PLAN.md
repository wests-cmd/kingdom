# Kingdom daily-driver delivery path: five engineering milestones

**Dated 2026-11-22. This is a release qualification plan, not a claim of completion.**

## Definition of done

A new user installs Kingdom on Windows, Linux or macOS without a terminal, selects an available model/harness, assigns work in natural language, sees the chosen tools and authorization scope, and can use the same computer normally while Kingdom works in a separately owned browser/virtual desktop. The UI shows actual task transitions, receipts, cost and stop controls. Jobs continue with the window hidden while the backend is awake. Unfinished work recovers safely after restart. When that computer is powered off, a separately powered and explicitly approved Knight may handle only self-contained eligible work. No feature silently steals foreground focus, clipboard, keyboard or pointer; no AI may grant itself authority.

A self-building harness is admitted only within isolated workspaces and an approved Git branch. Human authorization owns policy changes, permission changes, signing, production rollout and financial actions. Model text is neither proof of effects nor approval.

## Source truth

- Published public installer milestone: [v1.2.7](https://github.com/wests-cmd/kingdom/releases/tag/v1.2.7) on November 22, 2026. Older README installer links may still be pinned to 1.2.6; the GitHub release assets and hashes are authoritative.
- Existing owner policy, task and receipts: backend/runtime/engine.py, execution.py, tasks.py, agent_sessions.py, durable_automation.py, background_requests.py, and backend/security.
- Existing Windows foreground input: backend/runtime/desktop_control.py. This is **not noninterfering**.
- Existing tray: desktop/background.js; window close != process exit, but sleep/shutdown/logout are different lifecycles.
- Experimental browser candidate: [PR #185](https://github.com/wests-cmd/kingdom/pull/185); it is NOT part of published v1.2.7.
- Mandatory installed-machine independent security commissioning: [#172](https://github.com/wests-cmd/kingdom/issues/172), currently no verified YES results.
- Broader private native desktop executor: [#186](https://github.com/wests-cmd/kingdom/issues/186).
- Reliable unattended startup and remote continuity: [#187](https://github.com/wests-cmd/kingdom/issues/187).
- Owner-approval review [PR #173](https://github.com/wests-cmd/kingdom/pull/173) and SQLite/revocation concurrency review [PR #176](https://github.com/wests-cmd/kingdom/pull/176) must remain separate and unmerged until their required evidence passes.

## Engineering milestones: exact sequence

### 1. Repair the release candidate and prove portable unit contracts

- Normalize Windows/Linux/macOS paths; test no UI interaction enters the host input subsystem.
- Required quick tests: isolated-browser validation, readiness, dual permissions, receipt verification, and frontend request builder on all relevant CI runners.
- Block merging if a native platform test fails. Review exact head SHA, not a different PR run.
- **Exit: YES only if all current-head CI suites pass, with no skipped mandatory gate and no stale artifacts.**

### 2. Secure disposable browser interaction without touching the user desktop

- Use only a fresh headless context and an owner-configured list of exact domains; block private IP literals, localhost, service workers, downloads, permissions, arbitrary JavaScript, unsupported HTTP methods, redirects and WebSockets.
- Bind every browser operation to the existing live task guard; check again before each action and final capture. Single-attempt, local-only preview by default.
- Do not equate app-level network routing to OS isolation: a malicious website, browser exploit, DNS rebinding or a misconfigured proxy can still escape an inadequate host boundary.
- Deliver a separate unprivileged browser worker with enforced OS network egress, process/resource quotas, redacted logs and disposable credentials. Never use user Chrome profiles.
- **Exit: YES only with real network and filesystem isolation tests, prompt-injection containment, zero host input events, and independently verified action receipts. Current experimental PR is not this exit.**

### 3. Make execution continuously supervised, cancellable and restart-safe

- Reuse the single durable scheduler, request service, task identity and lease/fencing state. No shadow scheduler or second authority engine.
- After crash or power interruption, prove that idempotent steps can be reconciled and non-idempotent external actions become RECOVERY_REQUIRED rather than repeated.
- Implement supervised, opt-in OS service startup separate from the visible Electron window; logoff/desktop-lock must not unlock or access owner sessions.
- On user presence, yield CPU/RAM to the desktop, cap concurrent heavy jobs and refuse under-resourced workers.
- On primary-host shutdown, assign eligible independent jobs only to another awake authorized, paired Knight using the existing signed protocol.
- **Exit: YES only after real reboot/partition/revocation/rollback evidence and a sustained two-device soak test, with user-visible PAUSED / NEEDS_REVIEW / FAILED outcomes.**

### 4. Make the product understandable, interruptible and useful to beginners

- One native main window: Ask Kingdom, Working, Waiting for me, Completed, Computers, Knowledge, Settings. Advanced capabilities remain a secondary view.
- Show background mode, selected model/harness, chosen worker, exact tool permissions, budget, private-surface screenshot and independently verified result.
- Distinguish: browser-only preview, full isolated desktop control, interactive Windows foreground control, and remote Knight execution. Never label them all as "computer use" without explaining the differences.
- Implement a single persistent Stop/Pause/Emergency Stop control and readable approval cards that identify the precise host/site/action/data scope.
- Add guided no-terminal setup, keyboard accessibility, reduced-motion behavior, low-RAM warnings, recoverable onboarding, and a video showing **actual installed app** rather than an illustrated substitute.
- **Exit: YES only after novice task walkthroughs on clean Windows/Linux/macOS machines, screen-reader/keyboard checks, and 10 real representative workflows with verified outcomes.**

### 5. Certify, package, pilot and prepare either free distribution or a commercial edition

- Require all eight independent installed-system security gates in #172, plus no-desktop-interference, permission revocation, OS isolation, disaster recovery and clean installer tests.
- Release signed/notarized packages as applicable with exact hashes, protected updates, backup compatibility, fresh-machine install and rollback. Require real Apple Silicon/mobile testing before advertising those platforms.
- Run a small pilot with consenting operators; track support burden, crash-free sessions, real-world task success, CPU/RAM use, and clear failure reasons. Stop rollout on regressions.
- Publish a support/security policy, privacy and retention disclosures, vulnerability response process, safe telemetry opt-in and commercial terms. Review dependencies and third-party licenses.
- **Exit: YES only when the pilot meets explicit thresholds and an independent Q-Man/D-Man review signs off with records; no release sticker based on screenshots or mocks.**

## Q-Man / D-Man adversarial review questions

| Council loop | Claim | Q-Man proof needed | D-Man break test |
| --- | --- | --- | --- |
| 1 | Browser does not interfere | Separate headless session, no host input calls, real owner typing test | Move focus, use multiple monitors, lock screen, clipboard conflicts |
| 2 | Permission gates are real | Current owner grants, exact scoped task, persistent revocation | Prompt injection, self-approval, replay, stale actor, DNS/local-network escape |
| 3 | Background is durable | Task/lease identity, durable checkpoints, reboot evidence | Power failure mid-submit, split brain, stale task, duplicate external action |
| 4 | Works on weak machines | Measured CPU/RAM, thermal budgets and worker alternatives | Heavy Chromium load during normal user desktop operation |
| 5 | Public download is honest | Signed build evidence, correct version, real tests, documentation | Wrong installer, corrupted update, failed rollback, unsigned/blocked package |

Status vocabulary for each item: **YES** = repeatable real evidence attached; **NO** = observed failure; **NOT TESTED** = missing or mocked evidence. Never convert NOT TESTED to YES merely because CI passed.

## Distribution / licensing boundary

Kingdom currently uses the custom **CYA License v2.0**, allowing personal, educational and non-commercial distribution under its conditions but requiring permission for third-party commercial use. It is public-source, not automatically OSI open source. The copyright holder can choose to publish a free local edition, add a separate commercial agreement, or relicense original code, subject to all contributors' and dependencies' rights. Do not advertise unrestricted commercial reuse under the existing text.

Possible product editions (decisions, not deployed products):

- Local/community: installer and bounded local work without compulsory cloud account; user pays their own model/computer costs.
- Paid managed: optional reliable hosted Knight/relay, managed backup/sync/support, clearly itemized cloud costs and separate contractual terms.
- Enterprise/teams: identity-bound shared approvals, audit exports, support, controlled fleet management and admin tools.

Do not add subscriptions or payment claims before a real compliant billing provider, security review, cancellation/refund policies and end-to-end entitlement tests. No arbitrary price, revenue or 99% autonomy guarantee is justified by existing evidence.

## Current stop/go record

| Gate | As of 2026-11-22 |
| --- | --- |
| Native installer available | YES — v1.2.7 GitHub release assets exist; device-wide acceptance not implied |
| Foreground Windows control exists | YES — interactive adapter source; not proven robust general autonomy |
| Separate browser draft | SOURCE IMPLEMENTED, NOT RELEASED — PR #185 |
| Browser OS network sandbox | NOT TESTED / NOT IMPLEMENTED |
| Full isolated native GUI worker | NOT IMPLEMENTED — #186 |
| Wake/restart/off-machine continuity | PARTIAL — #187 |
| Real-machine eight security gates | 0/8 verified — #172 |
| Safe to sell as an unrestricted unattended desktop agent | NO |

**Engineering policy:** Finish the real vertical slice, test it adversarially, and then advance. Do not promote unverified capabilities into release copy, app-store claims or commercial packages.
