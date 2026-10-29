# Plain-language work programmes

A programme saves a bounded list of outcomes in sections. Kingdom's service owns
planning and execution review; closing the browser does not stop those loops.

## Flow

```text
owner list → saved outcomes → one model proposal → exact owner review
          → existing governed mission/backlog → retained acceptance receipts
          → separate reviewed section suite → next section
```

Planning and execution have separate controls. Automatic planning proposes the
next eligible plan; it never grants tools, approves a plan or enables the global
execution queue. Existing runtime, autonomy level and permission requirements
still apply. A blocked item is not a completed task.

Use headings ending in a colon or Markdown headings, followed by one outcome per
line. Limits are eight sections, twelve outcomes per section, forty-eight total.
An idempotency key prevents duplicate list creation after a lost response.

Each programme-bound acceptance must match its reviewed mission, version and
step. Section acceptance requires a separately reviewed `project_test` command,
distinct from component acceptance commands. This prevents accidentally counting
the same check twice; an owner still reviews whether the suite actually covers
the interactions. The supplied commit is an owner declaration, not a checkout
attestation. Passing command summaries do not prove general application quality.

## Recovery and limits

Interrupted planning and mission binding are retained for review and never
replayed automatically. A changed source, missing receipt or invalid prerequisite
invalidates downstream completion before the next work selection. Unknown action
outcomes require inspection, rather than expiry-based retries.

Bounded function checks retain their existing limited repair mechanism. Project
test commands execute once and are not automatically rewritten or repeated.
Arbitrary repository repair, skill installation, cloud-provider configuration,
fleet rollout and general autonomous coding are not established by this feature.
Missing capability must remain visible until a separately reviewed implementation
and receipt exist.

The lifecycle runner plans at most one proposal per cycle and suppresses repeated
identical error notices. It starts with the API service and cancels read-only
planning at shutdown. The execution backlog remains the only selector for tracked
missions, including when no browser is open.

## Adopt an existing saved backlog

Creating a new programme from text creates new work rows. Existing backlog notes
can instead be adopted through the owner-only `POST /work-programmes/adopt`
endpoint, so their work IDs, descriptions, priorities, task types and dependency
order remain intact. This is a handoff into planning, not permission to run notes.

The request requires an explicit project, idempotency key, section title, exact
owner-declared source commit and one to twelve note IDs with their current
revisions. For example:

```json
{
  "project": "kingdom",
  "idempotency_key": "queue-repair-v1",
  "title": "Queue repair",
  "source_revision": "0123456789abcdef0123456789abcdef01234567",
  "items": [
    {"work_id": "existing-note-id", "expected_revision": 1}
  ]
}
```

Use the actual current source and note IDs; these example identifiers are not a
reviewed execution target. Planner defaults are deliberative and local; the
existing configured-chat, ChatGPT handoff and cloud/mixed routing choices remain
available through their normal configuration fields. `auto_plan` starts false.

All selected notes must belong to that project, be disabled and unplanned, have
no mission binding, lease, completed evidence or programme owner, and match the
submitted revisions. Include the entire dependency set within the twelve notes;
external dependencies and cycles are rejected. No dependency is removed or
invented to make adoption succeed. Large backlogs need small, closed sections.

One transaction records ownership and adds a separate section integration gate
depending on every selected note. A failed transaction leaves no gate or partial
ownership. Two concurrent requests cannot take the same note. Repeating the
identical request returns the existing programme even after adoption changes
note revisions; changing its input under the same key is rejected.

Enable automatic proposal generation separately when its configured model is
ready. Model proposals still need the existing review, capability and acceptance
checks. The integration gate stays unfinished until a separately reviewed suite
tests the section together. Adoption supplies neither missing tools/models nor
independent test contracts, grants, release permission or evidence of completion.

## Planning checkpoints

Deliberative planning checkpoints each selected model **before** capacity waiting
or network I/O. Each stage exposes `phase`, `profile`, `hosting`, `started_at` and
`deadline_seconds`; this identifies the proposal attempt and does not establish
that model inference or a task is executing. A completed stage adds
`completed_at`, monotonic `elapsed_seconds` and the retained proposal text.
Failed attempts contain a fixed `error_category` and timing, never the provider's
exception text, response body, credentials or generated partial output. Fallback
attempt metadata is bounded by the existing three-connection shortlist.

Shutdown cancellation marks a stage interrupted. Startup recovery also changes
any retained running stage to interrupted while preserving its start time and
the programme attempt count; no inference, approval or execution is replayed.
Recovery duration uses wall-clock time and is labelled
`elapsed_basis: recovery_wall_clock`, since a process restart loses its monotonic
clock origin. The three-attempt programme budget and model timeout ceiling are
unchanged. These checkpoints diagnose waiting; they do not improve model speed
or establish that a model can produce an executable plan.

## Verification

Tests use real SQLite state, MissionService, TaskManager, governed process tasks
and test subprocess receipts. Model stubs exercise planner validation and
concurrency only; they are not evidence of a working local model. Live acceptance
must separately demonstrate the configured model producing useful reviewed plans
and Kingdom completing those plans without a Codex-driven advancement loop.
