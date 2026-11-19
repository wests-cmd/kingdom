# Kingdom runtime supervision redesign (2026-11-19)

Based on `main` plus `integration/kingdom-cohesion-20261119` changes.

## Root causes

The previous FastAPI lifespan started eight services sequentially *before* entering
its `try/finally` block. A failed `start()` could strand previously-created tasks.
`Scheduler._run()` did not contain exceptions from the tick handler; one unexpected
database or service failure could terminate task polling permanently.
`/health/ready` treated `len(node_registry.list_nodes()) >= 0` as proof of health
and did not check active background service or scheduler failures.

## Changes

- One `RuntimeServiceSupervisor` owns startup and shutdown of schedules,
  programmes, consultations, boss reviews, backlog, problem guide, Jules, and
  connected-peers service, along with controlled background request cleanup.
- Failed or half-completed startup reverses service startup order and stops
  the runtime scheduler; cleanup continues even if one service stop fails.
- Core `Scheduler` catches unexpected tick errors without granting additional
  execution authority. It records *exception type only*, uses bounded retry
  backoff, and emits rate-limited security-sanitized events.
- The readiness endpoint reports active lifecycle/scheduler failures with
  boolean flags and HTTP 503, without exposing private service information.
- The owner-only `GET /system/services` endpoint provides named service state
  and scheduler errors. The existing native-app Runtime page displays the same
  backend data; no second service-state implementation is created.
- Regression tests cover partial startup, idempotent start, interrupted stop,
  bounded scheduler retry, and owner-only status.

## Limitations and acceptance gates

A live service task can be `running` while internally returning failures; its
own durable error state and audit remain authoritative. This change does **not**
guarantee task exactly-once semantics or heal a multi-machine network partition.
Remote task completion, rollout, rollback, and installer testing remain separate
end-to-end gates. The repository's existing zero-trust and per-capability approval
checks remain the sole execution authority.

Promotion requires all backend tests and distributed process E2E, owner-access
security, native package builds, and representative 1/2/5-machine live tests. No
unexecuted tests should be reported as passing.

## Additional task-state seam

`RuntimeEngine._process_next_task()` previously published `task.running`
after claiming the durable task but **outside** the task's error/recovery
boundary. An event-bus exception could therefore strand the task in RUNNING
until the next process restart. The publish is now inside the same guarded
execution envelope; a failed event transition takes the existing
`retry_or_fail()` path. A focused regression test injects this failure.
