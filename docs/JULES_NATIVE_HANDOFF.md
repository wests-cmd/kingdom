# Native Jules handoff and exact-patch acceptance

The adapter is off by default. An authenticated owner configures credentials and
explicit source/repository allowlists through `/integrations/jules`. Credentials
are encrypted in SQLite with a separate service-owned key. On Windows that
master key is additionally wrapped with current-user DPAPI; POSIX retains mode
0600. Creation/migration is serialized across processes. DPAPI does not replace
tool/OS isolation and binds recovery to the original Windows user context. Responses never
return the credential. A job must reference an existing backlog record and has
an exact base revision, idempotency key, deadline and bounded repair budget.

The lifecycle runner submits and observes jobs separately from the backlog
runner. Atomic SQLite claiming prevents two service instances from both POSTing
the same job. An interrupted/unknown POST is retained for reconciliation; it is
never blindly replayed. Cancellation is local and does not claim that Jules
stopped remote work. A late successful POST retains cancellation and its session
identity. No automatic merge, deployment or PR export is requested.

## Acceptance boundary

Remote `COMPLETED`, human-review flags, model prose, passing test counts and
owner-supplied source labels are insufficient. The owner/controller first calls
`POST /integrations/jules/jobs/{id}/candidate`. Only artifacts retrieved from the
saved provider session/source can establish the candidate patch digest. A
different retained candidate requires a separately reviewed revision; it cannot
silently replace the one being tested.

`POST /integrations/jules/jobs/{id}/verify` accepts a version-2 `attestation`
envelope. A native `independent_review` mission step fixes the project, source,
base revision, contract ID/hash and minimum test count. It accepts no arbitrary
argv, generated inputs, filesystem destination, host placement or repair command.
The approved contract identifies the external controller's actual checks; it is
not a command to execute in the normal workspace.

The signed verdict binds the job, project, backlog item, mission/version/step,
source, base revision, patch digest and contract digest. Its execution records
`verdict_origin=external_controller`, pinned image/source/tree hashes and a
nonempty passing behavioral suite. A normal `project_test` summary cannot be
substituted. Consumption, job acceptance and waking an enabled waiting backlog
item share one transaction. The mission subsequently verifies that same receipt
through its normal advancement path; no native tool receipt is fabricated.

Waiting review creates neither a shell nor model task. Crash reconciliation
recognizes only the exact typed no-task waiting record or a currently validated
external receipt; malformed native records are not silently skipped. Waiting work is removed
from ready selection so independent ready work can advance. Acceptance only
wakes an enabled waiting item, never one the owner paused. Previously accepted
verdicts are checked at their retained acceptance time; current reviewer
revocation and mission/contract changes still invalidate them.

## Independent reviewer

The runtime reads public keys only from
`/etc/kingdom/independent-reviewers.json`. Its file and ancestor directories must
be root-owned, with no group/world write permission or symlink traversal. The
registry is absent by default and must be installed by an authorized operator;
there is no model/agent tool for creating reviewers. Each reviewer entry includes
`public_key` (base64 raw Ed25519), `enabled`, `projects`, `sources` and allowed contract hashes in `contracts`, under
`{"version":1,"reviewers":{...}}`. Disabled/out-of-scope keys fail closed.

The inline pytest gate does **not** issue independent signatures. Independent
review demonstrated that candidate imports can forge their own XML and exit
status without running assertions. The signer is disabled, including when its
config requests attestation. An earlier signing/interoperability experiment is
historical test evidence only and must not be treated as independent acceptance.

A production issuer must own a separate trusted verdict process that never
imports candidate code, cannot be written by it, and tests the candidate across
an explicit execution/data boundary. The candidate must not choose its test
contract or success signal. The native governed `independent_review` contract now separates external verdicts
from ordinary command execution. The external producer still needs independent
review and a real job test. Production reviewer trust remains unconfigured; this
is not yet an operational autonomous acceptance system.

## Current scope and provenance

The initial adapter came from Jules session `9784710610709854012`, candidate
SHA-256 `35a7bbda097015b9c4391e275a77223feaf41191ac0f15bb0c6c7a70fb3910db`,
base `ff0580644e79f8aa4fc73dd0e0272a5364e10dd8`. Independent checks found that
matching a base revision did not prove the returned patch had been tested.
Operator changes added signed patch acceptance, provider artifact retention,
backlog gating and cancellation/idempotency hardening. These changes are not
proof of autonomous Kingdom coding.

Tests exercise cryptographic substitution/revocation/expiry, the prior failing
artifact fence, a signed positive fixture, owner-only API access, atomic
submission, cancellation races and existing backlog/programme contracts.
Fixture-signed test data is a unit-test seam, not a real autonomous job receipt.
Protected production key installation, a real source-bound signed job,
external verdict issuance/mission execution binding, automatic failure handback, Boss placement, full release review and fleet rollout
still require their own evidence. Do not enable the whole backlog from these
module tests alone.
