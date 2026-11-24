# Verified status and remaining work

Published native release at this candidate snapshot: [v1.2.7](https://github.com/wests-cmd/kingdom/releases/tag/v1.2.7). It has versioned Windows, Intel macOS, Linux AppImage and Debian x86_64 installers, release manifest and SHA256SUMS. The latest source changes (user visibility and mesh-revocation hardening) have been merged **after** v1.2.7 and are being prepared for v1.2.8. Merging code does **not** replace existing published installers or update installed computers.

[PR #175](https://github.com/wests-cmd/kingdom/pull/175) (final Docker audit and v1.2.7 identity) is merged and included in the published v1.2.7 release. [PR #180](https://github.com/wests-cmd/kingdom/pull/180), [PR #182](https://github.com/wests-cmd/kingdom/pull/182), and [PR #183](https://github.com/wests-cmd/kingdom/pull/183) are merged to `main`; their visibility, event-timeline and atomic heartbeat changes require a **new** reviewed release before users can download them. [PR #173](https://github.com/wests-cmd/kingdom/pull/173) and [PR #176](https://github.com/wests-cmd/kingdom/pull/176) remain separate, unmerged security candidates. The eight installed-machine security tests remain [open and unverified](https://github.com/wests-cmd/kingdom/issues/172).

## Documentation and source navigation

Use the [documentation index](README.md), [architecture](ARCHITECTURE.md), [development](DEVELOPMENT.md) and [operations](OPERATIONS.md) as the current navigation. Detailed guides and dated audits remain in place; historical conclusions apply to their own source and environment.

## Desktop dependency security status

Published v1.2.7 includes the earlier known-compromise gate and the final Docker-image dependency audit introduced in PR #175. These controls reduce package-installation risk; they are **not** an OS-boundary security certification. Desktop installers remain unsigned (macOS is also not notarized). The PR #183 race fix passed 2,004 backend tests with 5 skipped and all three native CI platforms; that proof concerns source CI, not the already-published v1.2.7 download.

The required real-machine checks include malicious dependency containment, hostile Git isolation, self-approval rejection, RPC replay, persistent revocation, network destination policy, independent monitoring and rollback without resurrecting grants. See [security commissioning issue #172](https://github.com/wests-cmd/kingdom/issues/172); the installed evidence remains 0/8 verified.

## Verified foundations and release scope

- Separate Knight computer and Apprentice software-agent identities, host labels and editable coordination diagrams. Coordination lines do not themselves change execution placement or grants.
- Supported remote text/Python analysis with signed placement and independent controller checks. Syntax checks do not prove program correctness.
- Visible work status, bounded mission budgets, recorded receipts and background/reconnect foundations.
- Per-Knight release reporting and a saved desired release. Checking versions does not install software or grant access.
- v1.2.7 native publication is recorded at [the published release](https://github.com/wests-cmd/kingdom/releases/tag/v1.2.7); it does not include PR #182 or #183. Their exact-source tests passed [backend and packaging CI](https://github.com/wests-cmd/kingdom/actions/runs/44979802578) and [native Windows/macOS/Linux CI](https://github.com/wests-cmd/kingdom/actions/runs/44979802576), but require a new tagged build and checksums before installed release claims.

## Eight remaining acceptance areas

| Area | State | What still needs evidence |
|---|---|---|
| General autonomous coding | Partial | Repeatable real edits, fixed independent tests, scoped correction, interruption recovery and honest failure across varied tasks. |
| Remote Knight installation and updates | Partial | Complete adapters, verified artifact transfer, update/reconnect/rollback and unavailable-peer handling. Pairing alone gives no installation authority. |
| Cross-Knight vaults | Partial | Scoped synchronization, conflict/restart/revocation checks and balanced replication; keep secrets and project permissions isolated. |
| Deterministic-first routing and inference | Partial | No-model status answers, meaningful model/worker selection, measured concurrency, grounding and fallback acceptance. |
| Portable background continuity | Partial | Installed startup/reconnect and recovery without temporary developer tunnels; prove device behavior and expose missing dependencies. Local custom helpers are not automatically bundled product features. |
| Beginner/advanced usability | Partial | Narrow-window and half-screen review, clearer topology and onboarding, and accurate distinction between visual hierarchy and execution authority. |
| Stable release integration | v1.2.7 published; v1.2.8 candidate | v1.2.7 native assets and release evidence are published. The user-visibility and mesh-revocation changes on main are not yet in that release. Broader real-device installation, cross-Knight update/reconnect/rollback and hardware coverage remain separate acceptance work. |
| Shared architecture and adaptation | Partial | Cross-interface idempotent jobs, portable project memory, restart-safe automation, optional voice/perception/connectors and measured adaptation. |

There are eight broad areas with remaining acceptance work. A checkbox or percentage would not fairly represent their different sizes. The foundations above are separately verified; no claim that the project is otherwise finished.

## Boundaries and availability

Cloud providers, harnesses, payment accounts, signing services and hardware integrations are optional and require actual configuration. No live payment provider or universal autonomous repair is implied by a UI control. The unsigned native packages may be blocked by operating-system application-control policies; no bypass is supplied.

[Latest published downloads](https://github.com/wests-cmd/kingdom/releases/latest) · [v1.2.7 release notes](releases/v1.2.7.md) · [v1.2.8 candidate notes](releases/v1.2.8.md)
