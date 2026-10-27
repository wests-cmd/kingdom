# Owner emergency stop

`RuntimeEngine.emergency_stop('owner', reason)` is synchronous. The owner-only
HTTP interface is `POST /runtime/emergency-stop` with `{"reason":"..."}`.
The operator is determined by the authenticated endpoint, never a request field.
GET on the same path reports the current stop and its `stop_id`.

Before returning, one durable task-database transaction records a stop latch,
revokes every active lease, and moves leased/running/verifying tasks to
`RECOVERY_REQUIRED` with cancellation requested and a new task version. Queued
tasks stay queued. Their local and remote claim transactions refuse the latch,
including newly constructed managers. Autonomy reports zero and cannot be raised
while the latch exists. Late RPC results are rejected with 403; stale task caches
cannot commit completion against the new durable version. Same-process result
acceptance and stop are serialized with the dispatch lock.

Deferred local Apprentice execution rechecks admission immediately before tool
dispatch or model generation. The trusted runtime callback binds the durable
parent UUID and claimed task version, and rejects cancelled, stale or held work.
Clearing the stop latch therefore cannot revive an old deferred request.

This operation does not wait for a cooperative scheduler to finish its current
tool. It fences acceptance and further dispatch. It does **not** claim to kill
an already launched process on another computer, undo its side effects, cancel
an external provider's in-flight job, or stop an unrelated controller/database.
Interrupted side effects require independent reconciliation before another try.

An owner reset is explicit: `POST /runtime/emergency-stop/reset` with the current
`{"stop_id":"..."}`. A stale identifier is rejected. Reset leaves autonomy at
zero, leases revoked, and interrupted tasks held; a separate owner autonomy
change is needed for new work. It never automatically replays interrupted work.
Repeated stops have new identifiers, invalidating older reset requests.

The durable latch is written before the policy update. If that later update
fails, the call may fail but the committed task/lease stop remains enforced.
Reset must follow inspection through the authenticated status endpoint; restarting
the process does not clear a stop. No stop was invoked against owner production
workloads while implementing this feature.

The acceptance harness exercises real task persistence, durable lease managers,
RPC fencing, restart, stale completion, concurrent independent dispatch and
owner-only stop/reset HTTP routes. Only policy isolation and identity/transport
plumbing are substituted in tests. The original expected failures were observed
with `--runxfail`; their markers were removed after implementation passed.
