# Native finite external-review worker

The new `scripts/jules-native-review-worker.py` is an operator-owned supervisor,
not a Kingdom agent tool. It connects only to one configured local owner API port
at `127.0.0.1`, reads approved awaiting-review jobs, obtains the exact retained
candidate and current mission binding, and invokes the existing fixed protected
external-review producer. It does not submit provider sessions, run models,
install tools/keys, grant capabilities, merge, deploy or renew authorization.

**Coverage remains seven fixed API negative fences.** A passing result is not a
general functional test, full coding acceptance, or proof of production readiness.
The worker refuses another contract or a minimum test count outside that scope.

## Operator prerequisites (not installed by this change)

- A POSIX root-owned deployment of the five trusted scripts: this worker,
  `jules-external-review.py`, `jules-source-preparation.py`,
  `jules-external-oracle.py` and `archive-verified-source.py`. All ancestors must
  be root-owned and not group/world writable; no symlinks.
- A separately governed fixed public reviewer registry and private Ed25519 seed
  outside every candidate workspace, plus the exact approved producer contract.
- An independently protected immutable bare Git mirror containing the exact
  base commit, with no writable objects, alternates or lazy fetching.
- A previously installed pinned Docker image and existing normal Docker access.
  Candidate source is read-only and network-isolated. Production credentials
  and the worker token are never mounted into it.
- A private copied owner token for the local running Kingdom. Revocation or API
  refusal stops useful progress; the worker does not bypass or refresh authority.
- A private existing state directory and a finite operator-reviewed scope file.

Example shape, with placeholders that must be replaced through normal operator
review; this is not an installation command or new approval grant:

```json
{
  "api_port": 8014,
  "owner_token": "/var/lib/kingdom-review/control/owner-token",
  "signing_key": "/var/lib/kingdom-review/control/reviewer.seed",
  "repository_directory": "/var/lib/kingdom-review/mirror.git",
  "image": "sha256:<64 lowercase hexadecimal characters>",
  "state_directory": "/var/lib/kingdom-review/state",
  "reviewer_id": "owner-approved-fixed-fence-reviewer",
  "project": "kingdom",
  "source": "sources/github/wests-cmd/kingdom",
  "contract_id": "owner-approved-negative-fence-contract",
  "contract_sha256": "<exact current protected producer contract_digest>",
  "allowed_paths": ["backend/integrations/jules.py"],
  "deadline_at": 0,
  "max_reviews": 1
}
```

The deadline is an absolute unexpired Unix timestamp, at most 24 hours ahead.
Each producer run is bounded by the earliest job deadline, operator deadline and
one-hour producer limit. Budgets range from one to twenty isolated test attempt
reservations, including interrupted/held runs. The worker never resets them.
One binding permits at most two attempts: the initial run and one recovery retry.
The current fixed producer supports only the Kingdom source listed above.

After prerequisites and approvals exist, a one-shot invocation is:

```text
python3 -I /protected/scripts/jules-native-review-worker.py --config /protected/control/scope.json
```

`--watch` enables finite ten-second supervision until the existing deadline or
budget exhaustion. It creates no scheduled task or Codex automation. Read-only
reconciliation may continue within the same deadline after the execution budget
is spent. A new operator scope is a separate decision, never an automatic renewal.

## Actual state machine and recovery

```text
current exact retained material + approved fixed contract
  -> SQLite BEGIN IMMEDIATE claim of complete binding
  -> executing
  -> protected producer returns signed verdict after candidate cleanup
  -> delivery_reserved (persisted before owner POST)
  -> /verify for passing fences, /failure for a genuine failed verdict
  -> delivered only when current job retains that receipt ID and binding
```

The key covers every binding field: job/project/backlog/mission/version/step,
source/base revision, exact patch digest and contract digest. Concurrent or
restarted workers cannot start duplicate concurrent work. A root-state POSIX
`flock` covers the whole tick, including cleanup, testing and delivery. Another
process defers without network or container work. The SQLite ledger is kept
inside the private root-owned state directory and never pruned automatically.

If execution is interrupted, the serialized worker first invokes the trusted
producer's retained-intent cleanup. A completed attestation with a verified
cleanup marker resumes delivery without retesting. Without a completed
attestation, successful cleanup can permit one fresh isolated test attempt,
within the original global attempt budget and deadline. These fixed tests use
a network-none/read-only disposable API environment; this does not retry a
provider submission or assignment side effects. A second interruption stays
held. Cleanup failure blocks all new candidates. Expiration still allows required
cleanup but no new test or verdict delivery. An absent verdict cannot become a
pass. The review-material API must explicitly acknowledge
`delivery_protocol: kingdom.idempotent-verdict.v1`; older endpoints cannot start
a review. If an owner verdict POST has an unknown outcome, the worker first
performs GET reconciliation against current accepted evidence,
`repair_verdict`, or bounded repair history. It matches both receipt ID and the
complete binding. If it is not consumed, the same candidate is still awaiting
review, current material reaffirms the same binding and idempotent protocol,
and the original receipt/scope remain unexpired, it can repost the **identical
signed owner verdict**. At most three persisted delivery reservations are
permitted. This also recovers a crash after reservation but before POST. It
does not rerun tests or create another receipt/correction. A revoked or changed
binding remains held. This exception applies only to the receipt-idempotent
local owner verdict API; uncertain Jules provider submissions or correction
POSTs are never replayed.

The worker does not permit unbounded container retries, renew an expired
scope, delete a ledger to regain budget, switch test contracts, widen allowed
files, change the installed image, change the local API endpoint, re-pair nodes,
or manufacture successful results from model/pytest output.

## Validation and release limits

Unit tests inject transport and execution functions only through the Python
constructor. JSON cannot choose those seams. These tests validate lifecycle,
binding checks, local claim persistence, cleanup gating and bounded identical
idempotent verdict delivery;
their synthetic signatures/results are explicitly not producer or hardware
proof. A separate native fixture with the actual protected producer, local owner
API, immutable mirror and installed Docker image must pass before a provider
demonstration or unattended-use claim. No protected keys, reviewers or worker
services were installed by this source change.

An individual returned-patch receipt does not prove several patches work
together. Programme section gates containing `independent_review` components
reject the ordinary `project_test` path: that path tests the programme's
original declared checkout, rather than an independently reconstructed combined
returned tree. Combined-source reconstruction and a corresponding protected
integration contract are still required before such a section can pass.
