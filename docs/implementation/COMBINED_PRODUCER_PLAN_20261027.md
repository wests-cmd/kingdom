# Protected combined-source producer: implementation checkpoint

Status: design and blockers only. No producer, key, trust entry, image, service,
or acceptance gate was installed or enabled by this checkpoint.

## Inspected boundaries

- `scripts/jules-combined-source-preparation.py` reconstructs each retained signed
  component and then the ordered aggregate. Its record is preparation only.
- `scripts/jules-external-review.py` owns isolated Python startup, protected input
  chains, immutable bare mirror validation, a pinned installed Docker image,
  resource limits, retained cleanup intent, fixture authentication, signing and
  cleanup. Its `execute`/`_execute` are specifically a **single-patch V2** producer.
  Its contract digest pins four protected script files.
- `scripts/jules-external-oracle.py` runs trusted host-side assertions through
  bounded container-loopback probes. It never imports candidate tests, but its
  configuration and result schema require a single candidate patch hash. Its
  seven API negative fences do not establish general combined feature correctness.
- `backend/runtime/independent_contract_catalog.py` discovers protected component
  contracts. Its exact schema has no command/producer-kind field and matches
  reviewer `contracts`, not the new separate `combined_contracts` scope.
- `backend/runtime/combined_acceptance.py` verifies a separate combined receipt;
  it intentionally cannot provide actual execution or advance a programme.

## Why no wrapper was added

Passing an ordered-input hash as an alleged single patch, accepting an arbitrary
prepared directory, or re-signing a component verdict would misstate provenance.
Copying the full Docker lifecycle into a new wrapper duplicates security-critical
cleanup and recovery logic. Reusing it cleanly requires a reviewed change to the
existing protected producer/oracle and their pinned contract, not merely new
files. The current assignment permits new combined-specific files only.
There is also no installed task-specific combined contract to select. A new
wrapper would therefore be disconnected machinery rather than a proven slice.

## Smallest safe next implementation

1. Extract a protected internal exact-tree runner from the existing producer.
   Preserve all current single-patch behavior and tests. Only trusted controller
   code may supply a freshly reconstructed source tree, matching tree/archive
   hashes, fixed assertion suite and bounded original deadline. Do not expose a
   caller-selected executable, import path, command, network target or runner in
   JSON. Hash every trusted dependency in each versioned contract.
2. Add a distinct protected combined catalog with a fixed `/etc/kingdom` path,
   current root-owned non-writable ancestry, no symlinks, duplicate-free strict
   JSON and bounded data. Bind project/source/base, combined producer kind,
   exact trusted suite dependency hashes, exact command and minimum count,
   expiry and explicit coverage limits. Resolve its digest from canonical actual
   contents, not a supplied claim. Match current `combined_contracts` registration.
   Keep ordinary component discovery unchanged.
3. A new combined CLI must start with `python -I`, acquire the same exclusive
   resource lock, recover retained cleanup intents, validate protected inputs and
   re-run combined preparation from the exact mirror and ordered signed receipts.
   Never trust an existing checkout or preparation hash alone. Check current
   component expiry/revocation both before reconstruction and before signing.
4. Test that fresh aggregate with the runner: existing pinned image, no pull,
   network none, read-only candidate source, no host credentials/Docker socket,
   fixed memory/CPU/PID/tmpfs limits, private disposable fixture token, bounded
   logs and deadline. Assert the final source digest still matches. Complete and
   verify cleanup **before** emitting a successful combined attestation. Persist
   intent so a supervisor crash cannot leave an unaccounted candidate running.
5. Sign the exact `kingdom.combined-patch-test.v1` payload using a protected key
   outside the candidate. Use actual trusted assertion counts and the exact
   catalogue command, combined tree, preparation/order hashes and section binding.
   A failed/unknown test or cleanup outcome produces no passing receipt. Do not
   renew deadlines or replay unknown provider submissions.
6. Only after independently reviewing the producer, catalog and real isolated
   fixture should a separate change wire current programme state to the verifier.
   Preserve the original-checkout rejection until then. Owner review must decide
   whether the selected integration coverage is adequate for the requested task.

## Required verification before installation

- Real Git two-component fixture reaches trusted assertions against the exact
  aggregate; a conflicting aggregate fails before launch. Individually passing
  components with an integration regression must fail the combined suite.
- Wrong/reordered/omitted receipts, current revocation/expiry, stale base/tree,
  changed catalog command/hash, unregistered combined scope and writable/symlink
  protected paths must fail without a passing attestation.
- Assert no candidate tests/conftest/plugins are imported into the controller;
  a candidate printing fabricated success cannot affect trusted counts.
- Exercise process termination after intent, launch, verdict and cleanup phases;
  recover exact candidate identities, enforce mutual exclusion and bounded RAM,
  and never sign success while cleanup is unknown.
- Retain actual isolated run evidence and then exercise the combined verifier's
  signature, current-state, expiry and single-consumption checks. Unit signatures
  alone cannot substitute for this fixture.

Remaining implementation prerequisites: expand the next coding scope to refactor
the existing protected runner under review and version its contracts (ordinary
source work, requiring no new user approval), a reviewed task-specific suite/catalog, an existing
compatible pinned image, protected runtime cryptography, operator key/trust
installation, native fixture validation and a separately reviewed acceptance
transaction. None requires or authorizes bypassing the existing execution guard.
