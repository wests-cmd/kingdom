# Whole-project coherence programme (v1.3 development)

Baseline: `49ccc59b6782711da626bf861d9fa1e11e0c89fa`. Stable v1.2.11 remains untouched. This plan is not completion evidence. Extend the existing [completion ledger](completion-evidence.json) and [continuous completion directive](KINGDOM_CONTINUOUS_COMPLETION.md), not a parallel tracking or authorization system.

## Invariants

One product boundary and authority; one durable objective lineage; existing task repository and scheduler; no model self-grant; no replay of uncertain effects; independent acceptance and provenance; authorized clients use versioned contracts; installed evidence is distinct from CI; no mandatory LifeOS/Herdr dependencies. Multiple planners, adapters and observation runners may exist but cannot become independent execution authorities.

## Execution sequence and acceptance

| Slice | Existing ownership / interfaces to review | Ledger gate |
|---|---|---|
| Inventory | README, architecture, AGENTS, all routes, imports, dependency manifests, migrations, installer and release workflows; trace actual callers and flag unused code before removal | COHERENCE-01 through 09 |
| Runtime | request_service, tasks, repository, missions, agent_sessions, harnesses, work_programmes, scheduled_runner, API | COHERENCE-01 |
| Authority | security, approvals, runtime policy, cluster identity, leasing, tool executor, external integrations | COHERENCE-02 |
| Intelligence | commander, missions, mission_acceptance, work_programmes, independent contract catalog; LifeOS-inspired desired-state criteria and anti-criteria | COHERENCE-03 |
| Adapters | models/service, profiles, capacity, integrations, MCP, harnesses, skill grants; verified capability and fallback | COHERENCE-04 |
| Fleet | scheduler, node registry, topology, task leasing, supervisor, persistent harness identity; Herdr-inspired observed activity and resync | COHERENCE-05 |
| Knowledge | memory, vault sync, ingestion, portable skills, trust and quarantine | COHERENCE-06 |
| Improvement | self_build_guard, work programmes, remote build, patch acceptance, existing workshop; independent promotion | COHERENCE-07 |
| Clients | authenticated API, desktop, frontend, mobile, Centipede protocol; connection lifecycle and stale status | COHERENCE-08 |
| Delivery | desktop launcher/updates, Docker, scripts, native/mobile builds, release assets and installed security | COHERENCE-09 |

For each slice trace front door -> owner authorization -> durable operation -> placement -> effect -> receipt -> projection -> recovery. Record missing links and test the full journey. Reuse existing code first; consolidate or retire a duplicate only after caller and data migration analysis. Run regression, adversarial, restart and contract tests before advancing. A ledger row may be VERIFIED only when its dependencies are verified and immutable evidence exists. Source tests alone cannot certify physical tests. Q-Man challenges proof; D-Man challenges failure boundaries. The same ledger and CI validator apply across workstreams. Prioritize regressions, P0 then dependency-unblocking P1; if external evidence is blocked, record it and proceed with independent source work.

## Initial audit (not exhaustive)

The baseline has 1,113 tracked blobs, 315 backend files, 154 frontend files, 230 test files, 198 docs, 86 app files, 51 scripts and 21 desktop files. Startup has a central application supervisor and multiple specialized review runners. Keep that supervision boundary; inspect runners for overlapping execution and resource admission, do not infer duplicates from file names. Unified work projection observes four repositories, not the full programme/automation/fleet lifecycle. Mission acceptance progress is retained state, not independent outcome proof. Current direct admission and native harness reconnect remain incomplete. Existing installed security ledger has eight untested gates. Current release ledger permitted a security-ready classification without other P0/P1 requirements and permitted verified claims with unresolved dependencies; this slice strengthens validation without changing the existing evidence statuses.

## Acceptance campaign

One supported clean machine installs from published artifact; owner authenticates, configures a real model and submits a measurable objective. Prove task/approval/lease lineage, tool effect, independent receipt and UI refresh across all supported front doors. Connect a second approved Knight; test overload, connection loss, reconnect, controller/worker reboot, duplicate requests, stale leases, revocation, emergency stop, corrupted receipt and failed update/rollback. Test knowledge upload/retrieval and scoped skills across clients. Run a bounded self-improvement task against an isolated candidate and prove independent rejection of weakened tests and protected-policy edits. Record exact immutable revisions, artifact hashes, commands, actual outcomes, environments and remaining limitations. No signed package or real physical/model acceptance is inferred from CI.

### Client coherence slice

The existing desktop realtime client now owns at most one socket and retry timer, disposes both on authentication lifecycle cleanup, ignores obsolete callbacks and isolates event subscribers. On successful attachment the UI triggers the existing shared data refresh to reconcile durable snapshots. This is reconnect reconciliation, not guaranteed event delivery or persistent external agent-session support. Existing HTTP authorization and event bus remain authoritative; tests cover reconnect, stale callbacks, duplicate connections, cleanup and observer errors.
