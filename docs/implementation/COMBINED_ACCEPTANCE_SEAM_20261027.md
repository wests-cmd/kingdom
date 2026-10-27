# Combined-tree attestation verifier seam

Status: source-only foundation; not installed, exposed through an API, or connected
to programme acceptance. The existing external-patch integration rejection stays
in force. This is not a claim of autonomous completion or independently tested
functional correctness.

`backend/runtime/combined_acceptance.py` adds a separate
`kingdom.combined-patch-test.v1` signature domain. Its binding includes programme,
section, project, source, exact base, ordered component receipt identities,
preparation provenance, resulting combined tree, and the operator-reviewed test
contract. Component test signatures cannot substitute for this signature.

`expected_binding` rechecks all retained component signatures against current
reviewer scopes and original expiry windows. It compares their full bindings and
canonical envelope hashes with the ordered preparation record. Changing the
section, order, source, base, contract, or preparation invalidates the binding.
The preparation hash is provenance, not evidence that integration tests passed.

The combined verifier requires an enabled protected reviewer with an explicit
`combined_contracts` hash scope in addition to project/source scope. Existing
component `contracts` scope grants no combined authority. It requires the exact
reviewed command and combined tree, successful nonempty test counts, isolated
network, read-only source and completed cleanup, followed by a valid Ed25519
signature. Signed execution declarations still depend on a trustworthy producer;
the verifier does not independently observe their truth or assess test adequacy.

`CombinedReceiptStore` records a receipt and its binding exactly once using a
SQLite write transaction and uniqueness constraints. A trusted internal resolver
must derive the current owner-reviewed section and call `expected_binding` using
the same transaction. The callback is not a model/HTTP configuration interface.
It must load fresh component records and the current protected reviewer registry;
cached bindings or component trust snapshots do not satisfy that contract.
Reads recheck current signatures, expiry and revocation. There is no historical
`accepted_at` override. Recording publishes an event but neither advances work nor
publishes a release. An event-delivery failure after commit cannot replay the
receipt; a future integration should reconcile from durable state.
Single consumption also prevents replacing an expired verdict for the same exact
binding; a future renewal design requires separate review rather than overwrite.

## Prerequisites before enabling any programme advancement

1. Install a protected independent combined-tree producer, test contract and
   scoped reviewer key. Select task-adequate coverage through owner review.
2. Have that producer reconstruct and test the exact ordered returned source;
   attest only actual execution after cleanup. The preparation script alone is
   insufficient.
3. Implement and review a service-owned live-section resolver and acceptance
   transaction. It must obtain the owner-reviewed descriptor from the protected
   actual contract catalog and component receipts from the programme's current
   consumed component state. Arbitrarily supplied dictionaries are not proof.
   The contract hash is an identifier/pin, not a self-authenticating descriptor:
   the protected catalog and producer must bind the actual minimum count and
   command content. Check current grants, cancellation and section version there.
4. Wire programme advancement only after real isolated combined-source tests and
   negative integration tests pass. Keep the current guard until then.

Runtime dependencies are the backend's existing Pydantic and cryptography
packages. No dependencies are installed by this module. Protected registry
loading uses the existing POSIX-only root-owned registry rules; test fixtures
replace that loader solely inside tests.

Validation: `python -m pytest tests/test_combined_acceptance.py
tests/test_programme_acceptance_fences.py -q`. The new tests generate real
Ed25519 signatures over synthetic test declarations, exercise current state and
SQLite concurrency, and reject mismatches, replay, expiry and revocation. They do
not run a protected combined producer or demonstrate live integration coverage.
