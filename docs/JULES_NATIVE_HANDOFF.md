# Native Jules handoff and exact-patch acceptance

The adapter is off by default. An authenticated owner configures credentials and
explicit source/repository allowlists through `/integrations/jules`. Credentials
are encrypted in SQLite with a separate service-owned key. Responses never
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

`POST /integrations/jules/jobs/{id}/verify` accepts an `attestation` envelope.
It requires both current canonical mission acceptance and an independent runner
signature bound to the job, project, backlog item, mission/version/step, source,
base revision and exact patch digest. The signed execution records the pinned
image, source archive, patched-tree inventory hash, exact command and nonempty
passing suite. The command must match the reviewed mission's acceptance step.
Receipt consumption and job acceptance share one database transaction.

The backlog checks delegated patch acceptance separately before completing the
item. An older native command test cannot complete a pending Jules job.

## Independent reviewer

The runtime reads public keys only from
`/etc/kingdom/independent-reviewers.json`. Its file and ancestor directories must
be root-owned, with no group/world write permission or symlink traversal. The
registry is absent by default and must be installed by an authorized operator;
there is no model/agent tool for creating reviewers. Each reviewer entry includes
`public_key` (base64 raw Ed25519), `enabled`, `projects` and `sources`, under
`{"version":1,"reviewers":{...}}`. Disabled/out-of-scope keys fail closed.

The inline pytest gate does **not** issue independent signatures. Independent
review demonstrated that candidate imports can forge their own XML and exit
status without running assertions. The signer is disabled, including when its
config requests attestation. An earlier signing/interoperability experiment is
historical test evidence only and must not be treated as independent acceptance.

A production issuer must own a separate trusted verdict process that never
imports candidate code, cannot be written by it, and tests the candidate across
an explicit execution/data boundary. The candidate must not choose its test
contract or success signal. That governed isolated-review contract must also
match the mission/backlog acceptance protocol; the former hardcoded sandbox
pytest argv does not match normal native command execution. Until this path is
implemented and reviewed, the verifier is a tested consumer interface with no
configured production issuer, not an operational autonomous acceptance system.

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
