# Adaptive cluster preview

Kingdom's core is an adaptive AI harness that coordinates models, agents, tools and approved computers to complete tasks. This preview makes dependent distributed analysis missions usable; it is not a replacement stable desktop release.

## Included

- Durable single-slot computer reservations, serialized in SQLite across controller processes. Expired/revoked leases release capacity; fencing rejects stale results. Expiry alone does not terminate a remote process.
- Reviewed mission steps can require a specific computer for text or Python syntax analysis. Level 5 and current paired identity, capability and healthy capacity are required. An unavailable required computer pauses the mission rather than silently executing on the controller.
- Verified remote results now feed dependent steps and complete missions correctly. A dictionary result becomes JSON text for a downstream text input, not an invalid database value.
- Cluster placement considers fresh load and recent verified operation outcomes; occupied computer slots are excluded.
- Computer cluster shows actual assignments, reasons, leases and readable verified results. The guided mission editor offers approved compute computers for supported steps.

## Verification

Backend: 489 passed, one optional integration skipped. Frontend: 11 tests and production build passed. An additional real two-computer test passed with a Windows controller/worker and Linux worker on a separate computer through encrypted SSH transport. It used signed worker RPC, independent recomputation and a dependency-bound second task. The same scenario is included in the process-level tests; optional `KINGDOM_E2E_REMOTE_CONFIG` supplies private SSH configuration outside the repository. No mock runtime results were used.

## Scope and remaining release gates

Remote analysis parses or measures supplied text; it does not execute generated Python or run its tests. General remote builds, remote agent tool execution, model sharding, autonomous model tuning and reliable end-to-end coding clusters remain unfinished. Hosted/local model and installed harness connections retain their separate documented contracts. Do not present the preview as delivering those unfinished features.

The Linux source service can be updated with preserved owner data and rollback. Stable desktop distribution still needs final artifact/platform smoke checks and a legitimate Windows trust/signing path; do not weaken Application Control to install it. Keep stable downloads pointing to their tested version until those gates pass.
