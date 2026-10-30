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

The native Jules adapter can supply a failed candidate observation only after
rechecking the current mission, job/source/base/patch/contract binding, protected
reviewer trust, receipt expiry and atomic consumption of that failed verdict.
The retained patch bytes must still match the signed digest. Feedback exposes
bounded test identifiers, failure codes and counts; it does not copy provider
prose, commands, signatures or signing material. This read path submits no job
or repair and does not enable a worker.

Repair reservations retain an immutable note title and observation before note
creation, so a later verdict cannot collide with the same idempotency key after
a restart. A new verdict for the same candidate updates the current review but
does not rewrite that historical note or spend another note slot. Distinct
external candidate patches have distinct bindings within the same three-note
ceiling. Reserved notes remain disabled and require a separately reviewed plan.

An owner can adopt a repair note into a new programme or attach a separately
reviewed mission through the existing backlog controls. Later Boss cycles
reconcile its original project, idempotency key, title, description, priority,
task type and dependency provenance instead of registering its initial unbound
intent again. They preserve the note's identity and subsequent mission binding,
status, enablement and programme ownership without dispatching or duplicating
it. Changed original provenance or a partial mission binding holds review;
Boss never retargets a note or resets it to unplanned work.

The owner-only API has strict typed response schemas. Its receipt-review contract
requires `release_allowed: false`; a contradictory controller result fails
response validation rather than being presented as publication authority.

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

Native failed-verdict tests use fixture signatures and a fixture trust registry
around the real native job ledger. They test current receipt/patch binding,
revocation, expiry and cancellation; those signatures do not demonstrate that a
real external environment ran the fixture patch.

If an external receipt later expires or its reviewer is revoked, Boss records
the current acceptance as unavailable and holds. It preserves the original
patch-bound repair note and does not reserve another mission-only note or spend
another repair slot. Recovery-checkpoint tests reproduce this distinction with
real signed fixtures and retained `review_required` state. Missing trust is not
evidence of a newly failed candidate and never authorizes repair execution.
