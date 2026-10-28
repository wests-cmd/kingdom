# Scoped regression supervisor

This is an owner-installed adapter for **one contract**: regression tests for
`backend.cluster.shared_groups.remap`. It is not a general autonomous coding or
release system. The native-tool pilot generated a bad test; the supervisor's
bounded corrections also stopped for review. Those failures remain evidence,
not completed engineering work.

The adapter watches durable Kingdom requests, downloads their verified write
artifacts, rejects unsafe/irrelevant test syntax, and runs a nonempty unittest
suite in a temporary container made from a pinned existing local image. Each
container has no network, a read-only root and source mount, no capabilities,
no privilege escalation, a non-root user, and fixed CPU/memory/PID/time limits.
The model chooses none of these commands or flags and receives no Docker access.

Acceptance requires the test to pass against protected real source and fail
against three known regressions: unchanged mapping, metadata loss, and mutation
of the input. This establishes that specific regression contract, not arbitrary
application correctness. Configuration pins source hashes, computer identity,
the job's absolute deadline, and at most two repair requests. Each repair has a
distinct durable idempotency key. Old request budgets and exhausted job states
are never renewed automatically. Publication/release is not configured.

Keep configuration, supervisor and checkpoints outside all model-writable
workspaces. Install using ordinary existing OS authorization; do not use this
adapter to bypass a denied command or grant an agent host administration.
The DT1 pilot uses an independent owner-installed system service with
NoNewPrivileges and filesystem protection. The job state is retained separately
from the agent's claims. With explicit `publish_status: true`, bounded status is
also saved to the owner's local Kingdom project vault; diagnostic text remains
untrusted reference material.

`tool_protocol: structured` is an opt-in alternative for an explicitly ordered
tool sequence. Kingdom selects the current allowed tool, asks the model for
schema-constrained arguments, validates them independently, and submits the same
governed task used by native tool calls. It does not interpret free model text
as authority, accept parallel calls, change permissions, or bypass path checks.
All stages still require actual verified execution receipts.

Verifier self-tests must use a separate checkpoint root and
`publish_status: false`; fixture passes are not production task acceptance.
Automatic restart after ambiguous inference or an interrupted tool remains a
separate recovery concern. A terminal review/expired state requires inspection,
not a loop that increases its own budget.


For explicit structured file stages, `tool_paths` binds one workspace-relative
path per stage. Read/list stages dispatch the normal governed task without
model inference. Write stages ask only for content; a model-supplied path is
rejected. The existing workspace resolver still checks containment and symlinks
at dispatch. This reduces argument errors, not the independent correctness bar.


Verified bound file sequences finish with a controller-generated execution
summary instead of an additional inference. Completion still requires the
ordered tool receipts and every declared required tool; it is not application
acceptance. Provider failures and interrupted inference hold the independent
job without consuming code-repair attempts. Background deadlines propagate to
the agent with a maximum 600-second inner run; they are never renewed.
