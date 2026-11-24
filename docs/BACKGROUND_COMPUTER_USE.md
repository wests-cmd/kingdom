# Kingdom — Noninterfering Background Computer Use

**Engineering decision: 2026-11-22. Status: NOT public-release certified.**
Baseline: native v1.2.6 release and current main; source may include later, unreleased changes. Recheck every commit and artifact before release.

## Definition of done

A beginner installs a native Kingdom application without a terminal, starts a task, and sees verified progress while still using their own mouse, keyboard, apps and browser normally. The assistant can work with the window minimized, pause for approvals, and continue on separately powered computers when the owner's own machine is off. Important effects are auditable, reversible where possible, and never falsely reported as completed.

**A powered-off computer never executes anything.** Work continues only on another powered-on authorized worker or an explicitly configured hosted executor.

## Preserve and reuse

- Electron already keeps the owned backend running when the user closes its window to the tray. This is not login startup, a system service, or sleep-state execution.
- Kingdom already has authenticated tasks, durable scheduling, agent sessions, separate model/tool grants, approvals, signed Knights and recorded receipts. Never add another scheduler or approval authority.
- Windows foreground input and observation exist, but **foreground input can disturb the user**. It must remain an explicit interactive mode, not the unattended default.

## Computer-control modes

| Mode | Work surface | May interrupt the owner? | Status |
| --- | --- | --- | --- |
| Read-only process/health tools | Approved host telemetry | No pointer/keyboard changes | Existing scoped foundation |
| Private headless browser | Disposable Chromium browser context | No OS-level user-session input | Experimental, disabled by default |
| Private full desktop | Dedicated VM, OS session, virtual display or remote dedicated computer | Not if truly isolated | NOT IMPLEMENTED |
| Foreground Windows input | Owner's currently active window | Yes | Existing interactive path only |
| Remote worker | Another approved, powered-on Knight | No input into owner's computer | Existing foundation; full acceptance open |

Headless Chromium is **not** a complete OS security sandbox. Separate user/browser state avoids focus theft but must be combined with restricted egress, filesystem boundaries, credential isolation and a dedicated host/container/VM before mass-market unattended use. All model-supplied website content is untrusted.

## First experimental vertical slice

The new computer.browser.run@1.0.0 adapter works within Kingdom's existing native governed tool dispatch:
- Requires both computer.control and network.access capability grants and existing approvals.
- Disabled unless KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER=1 is explicitly set by the operator.
- Requires KINGDOM_BROWSER_ALLOWED_HOSTS to list exact owner-approved HTTPS destinations; model arguments cannot extend those destinations.
- Runs a fresh nonpersistent headless Chromium context, blocks service workers and downloads, and does not send host cursor/keyboard input.
- Supports at most eight bounded navigate actions by default. Click/fill/press require a separate explicit experimental interaction opt-in in a disposable test environment; GET requests can still have website side effects, so the application-level HTTP-method gate is not a financial or transactional safety guarantee. No arbitrary JavaScript, localhost, local file URL, wildcard host, or unreviewed browser profile.
- Saves limited rendered evidence and a screenshot whose digest is checked by the existing independent receipt verifier. Sensitive query credentials in URLs are rejected, query-string values are omitted from recorded destinations, and recognized credential patterns are scrubbed from recorded page text. This is best-effort redaction, not proof that a screenshot contains no secrets. The authenticated owner can download that private-only screenshot from the saved task result; tampered captures and paths outside the workspace are denied.
- A dedicated **Stop private browser task** control cancels queued work or atomically fences running/leased work, revokes the task lease and marks it RECOVERY_REQUIRED. It does **not** undo requests already sent to websites; the owner reviews them before a new attempt.
- Before Chromium launch the runtime requires at least 768 MiB available RAM. Low-memory workers report an actionable readiness blocker rather than launching a memory-heavy process over the user's active desktop.
- Does **not** certify actual external business effects or independent website correctness.

Playwright is an optional development dependency: install Playwright plus its Chromium browser *only for disposable testing*. It is NOT automatically bundled in the current end-user installers. Domain validation and browser interception alone do not prevent every network escape, including DNS rebinding, WebSockets, and browser protocol handlers. Production requires enforced network and OS isolation before enabling this feature for nontechnical users.

## Background and powered-off continuity

1. Tray hide: existing local service continues only while the machine is awake and the app/backend process exists.
2. Logoff/reboot: provision an unprivileged, supervised service. Reconcile persisted tasks, leases and approvals; never blindly replay a button click after an interrupted payment/post.
3. Sleep: pause or queue; optionally allow documented wake-on-LAN prerequisites.
4. Power off: move only independently safe and authorized tasks to another powered-on Kingdom Knight or hosted worker.
5. Owner returns: present completion evidence, approvals, screenshot of the *private automation surface only*, errors, costs and rollback.
6. Resource management: yield CPU/RAM to the owner, cap parallel browser sessions, stop runaway tasks, and refuse unsafely low-memory hardware.

## Daily-driver UX

The home screen should offer **Ask Kingdom**, **Working**, **Needs my approval**, **Done**, **Computers**, **Knowledge**, **Settings**. Give the user a single Stop/Pause/Emergency Stop path. Show clear activity and evidence, not hidden agent actions. Provide beginner/advanced views, accessible keyboard navigation, reduced motion, readable status, and privacy controls.

## Mandatory release acceptance (YES / NO / NOT TESTED)

1. **Real-machine security:** independent eight-gate commissioning in issue #172, not source tests alone.
2. **Noninterference:** no focus, clipboard, pointer, keyboard or private-screen capture interference while the owner types, switches windows, locks the session, or uses multiple monitors.
3. **Network/system isolation:** prove confinement against internal-address requests, DNS rebinding, redirects, WebSockets, untrusted Git/files and privilege escapes in a dedicated disposable environment.
4. **Authority:** per-site, per-account, per-action approvals; revocation survives restart; no model-generated approval; owner sees and can cancel actions.
5. **Actual tasks:** complete at least ten real, independently checked workflows, including failure/denial and approval cases.
6. **Recoverability:** verify restart, power interruption, network partition, worker loss and rollback; non-idempotent effects are never blindly repeated.
7. **Performance:** measure sustained operation on ~4 GB dual-core systems and ordinary Windows/Linux/macOS, including CPU/RAM and owner responsiveness.
8. **Release engineering:** published signed/notarized installers where required, verified versions/hashes, clean install, rollback, accurate README and onboarding video, no terminal.
9. **Privacy and compliance:** local account separation, consent, secure credential vault, retention/export/deletion, telemetry opt-in, disclosures and vulnerability response.
10. **Commercial readiness:** real onboarding, support, licensing/payment if monetized, actual operating-cost benchmarks and a paid feature people genuinely need. A free local/community tier and optional paid hosted worker/relay are product options, not implemented billing claims.

Each acceptance record requires exact SHA, build, OS, hardware, test procedure, expected result, observed evidence, failed/blocked cases and independent reviewer conclusion.

## Delivery order

P0: resolve security PR conflicts and issue #172; secure isolated browser egress, prove no interference.
P0: implement private native-desktop VM/session execution with governed actions and user-visible preview.
P0: complete durable restart-safe scheduling, remote worker failover, installed service lifecycle.
P0: finish user UX, installer signing, network security, recovery and real multi-machine tests.
P1: public beta/pilot and fix observed failures, then commercialize only proven support/hosting capabilities.
P2: broaden to mobile, Apple Silicon and additional OS automation providers after verified local-first foundation.

**Current position:** Kingdom has published native v1.2.6 with partial agent/background features. The isolated browser is an experimental PR; it is not a production-ready, independently certified unattended computer controller.
