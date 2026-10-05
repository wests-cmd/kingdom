# AgentScope addition progress

The authoritative scope is [the 55 Kingdom additions plus accessibility](AGENTSCOPE_ADDITIONS.md), confirmed by the owner on 2026-10-04. This work extends Kingdom. It does not introduce Centipede ISO or operating-system packaging.

## Implemented first batch

- **56, accessibility (partial):** selectable high contrast, 90–200% display size, large controls and pointer, visible keyboard focus, reading spacing, reduced distraction and motion. Four customizable starting presets require no diagnosis. Controls work before owner sign-in and on device connection pages. Worker cards are keyboard buttons. Page navigation focuses a main landmark and provides a skip link.
- **56, durable preferences (partial):** validated owner-only SQLite preferences, independent of permissions. Local preferences remain usable without backend access. New default devices can load the owner's saved preferences; existing local customization takes priority. Saves are serialized to avoid older requests overwriting newer settings.
- **1 and 50, operational recovery (partial):** actual readiness/runtime status, persisted restart plans, explicit owner approval, five-minute expiry, single-use claims, a single running repair, recorded outcome and restart verification. This action uses the existing runtime stop/start services. It does not patch code, change policy or install updates. An interrupted running repair blocks another repair pending investigation.
- **54, truthful repair reporting (partial):** legacy repair/recovery placeholders now report unsupported instead of falsely reporting success.
- **19–20, durable workflow checkpoints (partial):** the existing checkpoint manager now saves validated, versioned snapshots to SQLite, including completed steps, contract state and consumed budgets. A separate-process test verifies restart restoration. Invalid writes preserve the previous snapshot, and unsupported stored formats fail closed. Loading a snapshot does not execute a workflow or authorize a resume.

## Verification

- Clean Docker production build, including the frontend build.
- 294 Python tests passed on Windows and in a network-isolated Linux Docker container.
- The durable checkpoint batch increases that suite to 296 tests, passing on Windows and in Linux Docker. The first checkpoint Docker run had one distributed lease failure during a VM wall-clock discontinuity; retained event timestamps show the clock moving backward and then forward beyond the lease expiry. The isolated process test and full suite both passed after stabilization. Clock-discontinuity recovery remains an item for the partition/chaos matrix.
- Six frontend tests passed in Docker, including stored preference validation, CSS injection rejection and contrast checks.
- Browser user test at 200%: pre-login controls, owner sign-in retaining preferences, settings saved, no document horizontal overflow at the tested desktop width, keyboard Enter to review/approve a real runtime restart, and recorded verified outcome. The test used an isolated container, not the owner's installed database.
- Preference reload across container restart verified. Screenshots and Docker XML evidence are retained in the workspace `outputs/agentscope` directory.
- Final v1.1.2 batch: 305 backend tests passed on Windows and Linux Docker; eight frontend/mobile tests passed. All three native installer checks passed on the final PR head. The publication gate also requires native high-contrast, 200% size, no horizontal overflow, owner preference storage and reload evidence.
- The updated browser user test verified a three-word text-analysis result, keyboard worker selection, reviewed and separately approved runtime recovery, and accessibility controls while the test backend was stopped. Local selections survived reload and reconnection.

These checks are not a full screen-reader, switch, dwell, eye-tracking, speech/caption or WCAG certification. The v1.1.2 native publication workflow verifies the merged source independently, publishes platform evidence and screenshots, and checks downloaded release bytes against SHA-256 before publication. Existing v1.1.1 installers do not contain this batch.

## Remaining work and existing foundations

All 56 requirements remain open for their full acceptance criteria. Reuse existing services before adding parallel implementations:

| List items | Existing foundation / next gap |
| --- | --- |
| 1–4, 50–51 | Operational restart added; transactional server updater exists. Signed live/component updates, known-good certification, repair memory, safe deployment and update dashboard still require work. |
| 5–18, 22 | Runtime, workers, scheduler and routing exist. Full commander teams, delegation/handoff contracts, verifier aggregation, reassignment and resource-budget enforcement need end-to-end audit and implementation. |
| 19–23 | Workflow contracts, budgets and durable checkpoint snapshots exist. Full workflow execution/resume integration, current permission revalidation, checkpoints around every side effect and history/rollback remain open. |
| 24–28, 31 | Capability, approval, zero-trust, policy and model routing services exist. Audit every execution path and revocation/fallback boundary against the list. |
| 29–30 | MCP integration exists; protocol-complete governed MCP/A2A gateways are not certified. |
| 32–36 | Portable skill maps, trust/install tests, profiles and API discovery exist. Complete quarantine/sandbox lifecycle and catalog freshness evidence. |
| 37–40 | Signed node pairing, leases, fencing and restart reconciliation exist. Full commander failover and partition chaos certification remain open. |
| 41–47 | Prompt firewall, credential broker, memory services, events and telemetry exist. Verify live streams, execution trees and OpenTelemetry export; module presence is not certification. |
| 48–49 | Database readiness and security views exist. Comprehensive real health and security incident acceptance criteria remain open. |
| 52–55 | Existing regression/native packaging gates remain active. Expand doomsday, chaos, truth and certification checks for all new requirements. |
| 56 | Complete assistive-technology interaction, accessible critical flows, timing controls, optional voice/switch input and release certification matrix. |

No list item is marked fully complete merely because a module, screen or unit test exists.
