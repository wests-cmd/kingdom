# Swarm groups and native peer analysis

The network view presents one Kingdom containing named computer Knights. It
counts online and disconnected/unknown computers separately. Offline computers
remain visible with a dashed card until the owner's list timeout: seven days by
default, configurable between 12 hours and ten days. Archiving only hides a
computer from the main list; identity, pairing, grants and group membership are
retained. Fresh verified peer reports bring it back automatically.

## Diagram controls

- Drag a Knight onto another Knight to open a named group with both selected.
- Drop onto a group to edit membership; drop onto Ungrouped to remove membership.
- Right-click or select a card for its context menu. Touch/keyboard users can use
  the same action buttons. Work, Apprentice and service reports open in a dialog.
- Make group offers checkboxes for known members. Other-group Knights appear
  last, gray but selectable. Selection asks to move them; bulk selection asks
  once before saving the moves. Canceling a dialog changes nothing.
- Edit name, members, leader, flags and preferred work types in one dialog.
- Combine several groups into one; split into named nonempty groups. Remainders
  go to the first groups. Each split group starts with its first member as leader.
- Dissolve releases members without deleting computers. A move repairs a source
  group's leader if needed, and removes an empty source group.

Backend edits are one SQLite transaction with an expected snapshot version.
Stale screens get a conflict, not an overwrite. A Knight belongs to at most one
organizational group in the shared layout. Existing overlapping legacy groups must
be resolved explicitly. Group edits do not change grants, workload policy or
operating-system permissions.

When mesh membership is configured, its existing owner-selected authority stores
one organizational layout. Authenticated owners on approved member Knights send
signed edits to that authority. Requests and responses are bound to each other,
the expected peer identity and the normal durable replay checks. Canonical IDs
refer to actual computer identities; each screen maps its own identity to This
Knight. Concurrent stale saves are rejected. Offline clients show their last
verified layout read-only and never save a competing local layout. Legacy
single-controller group mutation endpoints reject edits while shared membership
is enabled. A standalone installation still uses its local layout.

The private peer listener needs explicit `groups_enabled` opt-in. This exposes
organizational group requests only, not execution, permission or autonomy RPCs.
Shared group editing is not the King/Commander authority feature: scoped role
enforcement is still a separate, unfinished integration.

## Actual work consumption

Previously the maintained peer link exchanged heartbeat/inventory data but did
not run a native task consumer. A queued analysis could remain queued despite a
green connection. The connection lifecycle now runs a bounded pure-analysis
consumer after verified reconnection. It needs a running safe-analysis or bounded
runtime (levels 1, 3, 4 or 5; paused and approve-every-task modes are held),
an installed coder with compute permission in both local permission stores,
an approved peer compute grant, fresh health, battery and capacity checks.

Only literal text analysis and Python syntax analysis are supported. There is no
shell, model inference, arbitrary code execution, container creation or grant
change in this consumer. It polls at most one supported task, validates exact
assignment/lease/fencing, stores a bounded durable result, and submits a signed
result for independent controller recomputation. An exact repeated lease reuses
the durable result. A failed analysis does not turn a healthy connection red.
Native polls ask the controller to honor its stopped runtime state.
An operator-installed private listener must explicitly opt into `analysis_enabled`;
its default continues to permit reports only. Even with opt-in, other execution
RPCs and non-analysis tools remain unavailable through that listener.

This closes a specific autonomous dispatch gap. It does not demonstrate general
repository editing, independent engineering review, integration testing or
automatic release. Those require their own actual receipts.

## Background agent continuation

The server's request loop now observes the exact durable tasks an agent is
waiting for. Once they finish, the same agent collects and verifies their
receipts before its next model turn. Waiting shares the existing 310-second
deadline and six-chunk budget. It does not resubmit tools, switch agents, retry
failed tasks, approve operations or restart ambiguous model turns. Missing,
approval-held, failed and recovery-required tasks still stop for review.
This removes a premature stop after tool dispatch; it does not establish the
whole autonomous engineering-and-release cycle or unattended restart recovery.

Authenticated callers can now explicitly choose 30–1800 seconds and 1–12
chunks when starting fresh work. The conversation UI offers short, standard,
15-minute and 30-minute limits. The original default remains 310 seconds and
six chunks. Deadline and consumed chunks are retained in the request record;
starting another runner cannot renew an expired or exhausted request. Model
timeouts and agent turn limits still apply independently.

For a reviewed scoped workflow, `tool_sequence` can name up to eight ordered
stages, for example read → write → read. Only the next stage's tool is offered,
and the stage advances only after its actual governed receipt is verified.
Premature completion, skipped stages and multiple calls are rejected. This
reduces schema/context overhead and keeps small models from selecting parallel
operations in a serial workflow. It neither creates the plan nor approves its
tools; process and desktop stages keep their existing separate requirements.

The optional `serve-approved-local-model.py` TLS relay remains text-only by
default. An operator may explicitly allow `workspace_read`, `workspace_list` and
`workspace_write` schemas for tool-call generation. Unknown/process tools,
duplicate schemas, oversized input and inference resource overrides are rejected.
The relay generates model responses only: the requesting Kingdom validates and
executes any returned calls under its existing permissions. This option does not
grant a tool, execute code, change TLS trust or download a model.
