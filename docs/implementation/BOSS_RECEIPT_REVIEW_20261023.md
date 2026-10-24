# Boss receipt review: implemented boundary and next gates

Boss is now a Kingdom-owned controller, started and stopped with the backend.
Every ten seconds it reviews up to the latest 100 saved work programmes on a
worker thread. Closing the browser does not stop it. It does not require an LLM
to compare retained evidence. SQLite stores its last changed review and bounded
repair reservations; unchanged cycles do not create new revisions or events.

The programme view shows the reviewer, configured planning/execution model
profiles, requested computers, step kinds, current receipt IDs and blockers.
Requested placement is explicitly distinguished from worker acknowledgement.
The owner-only `/boss-reviews` endpoint exposes the same retained review.

## Actual transition

```text
saved programme -> needs plan / owner review / working
current local passing component and separate integration receipts
  -> needs independent test (release remains held)
missing or failed current acceptance
  -> disabled repair-planning note with exact mission/version/task/report state
  -> at most three distinct failed bindings per programme
  -> repair budget exhausted; owner review required
```

Boss reserves a deterministic repair key before creating the note. A crash
between those operations is reconciled on the next cycle without replaying the
task or duplicating the note. Repair notes have no mission, approval, grants or
enabled execution. They are concrete feedback for the next reviewed plan, not
automatic successful repairs. Raw process output and provider credentials are
not copied into notes or the event bus.

## Deliberately unfinished

The existing project-test receipt validates a local command and nonempty passing
summary. Its source revision is an owner declaration; it does not independently
attest a checkout, a different machine, a separate environment, or code quality.
Consequently Boss cannot mark this pipeline independently tested or publish it.
`release_allowed` is always false. Two same-host commands cannot satisfy the
independent Knight gate. A model profile named `auto` is a configuration choice,
not evidence that a model ran or acquired missing tools.

Remaining work requires a trusted source/environment attestation path, a worker
plan acknowledgement protocol, explicit independent reviewer assignment and
signed acceptance, current tool/model readiness, and a separately authorized
GitHub adapter. General code changes, automatic repair-plan approval, AI source
review and automatic tool installation are not implemented by this slice.
Boss never raises a policy level or grants tools to finish a task.

Reviews retain their timestamp so an unavailable or stopped controller cannot
appear continuously current. Runner failures emit a generic `boss.runner_error`
event; invalid programme/receipt reads emit `boss.review_held`. Previously saved
reviews remain historical observations, never publication authorization.

## Evidence

Focused tests use the actual MissionService, TaskManager, governed process tool,
fixed unittest files, on-disk receipts and SQLite. They execute real local suites,
remove real receipts, verify revalidation and no duplicate work, exercise the
three-note budget, restart after a note reservation, and check owner-only access.
They do not use model output as successful execution evidence. A passing test of
this controller is not an autonomous live-fleet demonstration.
