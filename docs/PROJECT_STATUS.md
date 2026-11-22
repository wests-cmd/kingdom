# Verified status and remaining work

Published native release: [v1.2.7](https://github.com/wests-cmd/kingdom/releases/tag/v1.2.7), published November 22, 2026. The release has Windows, Intel macOS, Linux AppImage and Debian x86_64 native installers, plus evidence files, a release manifest and SHA256SUMS. It updates the Docker dependency audit/inventory and version metadata. The exact published artifacts are **not** automatically replaced when main or a candidate branch changes.

This document records the v1.2.7 user-download checkpoint. [PR #175](https://github.com/wests-cmd/kingdom/pull/175) is merged and v1.2.7 is published. [PR #173](https://github.com/wests-cmd/kingdom/pull/173) (approval hardening), [PR #176](https://github.com/wests-cmd/kingdom/pull/176) (SQLite/mesh/revocation) and [PR #185](https://github.com/wests-cmd/kingdom/pull/185) (experimental private browser) are **unmerged candidates**. Do not describe them as installed v1.2.7 features. The eight installed-machine security tests remain [open and unverified](https://github.com/wests-cmd/kingdom/issues/172).

## Documentation and source navigation

Use the [documentation index](README.md), [architecture](ARCHITECTURE.md), [development](DEVELOPMENT.md) and [operations](OPERATIONS.md) as the current navigation. Detailed guides and dated audits remain in place; historical conclusions apply to their own source and environment.

## Desktop dependency security status

Published v1.2.7 includes the known-compromise dependency gate merged in PR #171, audited desktop dependencies and versioned release checks, plus the final-container dependency audit improvements from PR #175. These controls reduce package-installation risk; they are **not** an OS-boundary security certification. Independent code-signing and macOS notarization are not established by these checks; follow the published installer warnings rather than bypassing OS protections.

The required real-machine checks include malicious dependency containment, hostile Git isolation, self-approval rejection, RPC replay, persistent revocation, network destination policy, independent monitoring and rollback without resurrecting grants. See [security commissioning issue #172](https://github.com/wests-cmd/kingdom/issues/172); the installed evidence remains 0/8 verified.

## Verified foundations and release scope

- Separate Knight computer and Apprentice software-agent identities, host labels and editable coordination diagrams. Coordination lines do not themselves change execution placement or grants.
- Supported remote text/Python analysis with signed placement and independent controller checks. Syntax checks do not prove program correctness.
- Visible work status, bounded mission budgets, recorded receipts and background/reconnect foundations.
- Per-Knight release reporting and a saved desired release. Checking versions does not install software or grant access.
- v1.2.6 native Windows, Linux and Intel macOS installer verification and publication passed in [run 44926235976](https://github.com/wests-cmd/kingdom/actions/runs/44926235976); v1.2.7 native installer assets are now separately published. Neither certificate proves every physical machine, OS signing or autonomous security boundaries.

## Eight remaining acceptance areas

| Area | State | What still needs evidence |
|---|---|---|
| General autonomous coding | Partial | Repeatable real edits, fixed independent tests, scoped correction, interruption recovery and honest failure across varied tasks. |
| Remote Knight installation and updates | Partial | Complete adapters, verified artifact transfer, update/reconnect/rollback and unavailable-peer handling. Pairing alone gives no installation authority. |
| Cross-Knight vaults | Partial | Scoped synchronization, conflict/restart/revocation checks and balanced replication; keep secrets and project permissions isolated. |
| Deterministic-first routing and inference | Partial | No-model status answers, meaningful model/worker selection, measured concurrency, grounding and fallback acceptance. |
| Portable background continuity | Partial | Installed startup/reconnect and recovery without temporary developer tunnels; prove device behavior and expose missing dependencies. Local custom helpers are not automatically bundled product features. |
| Beginner/advanced usability | Partial | Narrow-window and half-screen review, clearer topology and onboarding, and accurate distinction between visual hierarchy and execution authority. |
| Stable release integration | Released; wider device acceptance open | v1.2.7 native assets and release evidence are published; see its manifest for exact scope. Broader real-device installation, cross-Knight update/reconnect/rollback and hardware coverage remain separate acceptance work. |
| Shared architecture and adaptation | Partial | Cross-interface idempotent jobs, portable project memory, restart-safe automation, optional voice/perception/connectors and measured adaptation. |

There are eight broad areas with remaining acceptance work. A checkbox or percentage would not fairly represent their different sizes. The foundations above are separately verified; no claim that the project is otherwise finished.

## Boundaries and availability

Cloud providers, harnesses, payment accounts, signing services and hardware integrations are optional and require actual configuration. No live payment provider or universal autonomous repair is implied by a UI control. The unsigned native packages may be blocked by operating-system application-control policies; no bypass is supplied.

[Published downloads and exact build evidence](https://github.com/wests-cmd/kingdom/releases/tag/v1.2.7) · [Release notes](releases/v1.2.7.md)


## Daily-driver candidate — not released

The [five-milestone daily-driver plan](DAILY_DRIVER_SHIP_PLAN.md) and [noninterfering computer-use boundary](BACKGROUND_COMPUTER_USE.md) identify work still required to sell or mass-distribute Kingdom as an unattended AI operator. The experimental browser in PR #185 remains opt-in, locally scoped and **not OS-sandbox certified**, despite source tests. A separately isolated native desktop is not yet built. Background tray work on an awake computer must not be mistaken for execution while powered off.
