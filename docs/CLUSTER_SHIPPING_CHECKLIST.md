# Adaptive cluster shipping checklist

Kingdom is an adaptive AI harness across models, agents, tools and approved computers. A chat response, connected computer or passing process alone is not proof that an owner's task completed.

## Current execution boundary

The remote Knight daemon accepts `text.analyze@1.0.0`, `code.python.analyze@1.0.0`, and `provider.metadata@1.0.0`. Automatic offloading currently selects only text and Python syntax analysis, under the coordinated-missions autonomy policy. Provider metadata requires its separate reviewed-provider permissions and configuration. Python syntax analysis parses source; it does not run the source or its tests. Model server connections and external harness adapters are separate execution paths; pairing a computer does not remotely install a harness or grant arbitrary shell access.

The Computer cluster page shows persisted task assignments, lease presence, results and verification summaries alongside reported heartbeat, health and CPU/memory load. Current-task fields are reported node state; task records are the assignment evidence. No load report or status badge certifies job completion. The task list shows the latest 20 matching records; Tasks retains the broader history.

## Required release evidence

- [ ] Record tested source revision, platform, installed artifact checksum and configuration without credentials.
- [ ] Pair two real computers and grant only required capabilities. Demonstrate a real supported remote task with controller-verified output and the correct executing identity.
- [ ] Demonstrate competing tasks respect computer capacity/reservations. Record waiting or fallback reasons.
- [ ] Demonstrate a dependency-aware mission does not advance on failed or unverified prerequisites.
- [ ] Disconnect a leased worker, recover or explicitly fail the task, and reject the stale worker's late result without duplicate completion.
  - RPC acceptance coverage: `tests/test_autonomy_acceptance.py::test_stale_worker_result_is_rejected_after_reassignment` uses real task/lease persistence and result handler with identity/transport plumbing patched. It rejects both the old lease and a substituted new lease ID with the stale fence. This is not the physical-disconnect release receipt.
- [ ] Verify owner emergency stop on installed artifacts, including restart and late-result rejection. Runtime acceptance coverage is in `tests/test_autonomy_acceptance.py`; see `implementation/EMERGENCY_STOP.md`. Passing source tests does not establish fleet deployment.
- [ ] Revoke a computer during queued work and show that it cannot claim another task.
- [ ] Verify local fallback remains within approved scope and does not silently change a required remote target.
- [ ] Exercise malformed/tampered results and confirm they cannot count as verified success or improve routing.
- [ ] Run backend regression tests and the frontend production build on the final revision; record actual results and unresolved failures.
- [ ] Smoke-test installed artifacts, upgrade/restart persistence and owner access on every advertised platform. Build success alone does not satisfy this gate.

## Claims that require additional implementation and proof

General remote builds, remote native agent tools, arbitrary project splitting and model-weight sharding must not be advertised as supported by the analysis daemon. Before claiming a general coding cluster, implement a governed adapter, bind its inputs/artifacts to source revision and lease, independently check results, and demonstrate a real multi-computer implementation/review mission. Persistent routing outcomes are bounded placement evidence, not automatic model training or proof that skills improve performance.

Use `ADAPTIVE_CLUSTER_CORE.md` for the larger direction. Mark a gate complete only with receipts for the final candidate; do not infer release readiness from this checklist's existence.
