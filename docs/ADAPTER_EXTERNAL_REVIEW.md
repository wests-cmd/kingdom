# Fixed external adapter-readiness contract

`adapter-readiness-v2` is an operator-owned extension of
`scripts/jules-external-review.py`. It is not a candidate command or a general
claim that arbitrary engineering work is correct.

The protected controller reconstructs the exact Git base plus retained patch,
pins its source tree and installed image, and starts one non-root, read-only,
network-isolated candidate with bounded CPU, RAM and process count. The signer
and fixed assertions stay outside that container. Candidate source, test files,
pytest plugins, JUnit and success prose are never imported or used as verdicts.

The finite scope is the eight original adapter implementation/UI/docs/test paths
plus `frontend/tests/adapterDiscovery.test.js`. The controller checks the exact
allowlist, rather than accepting paths named by the patch. The contract digest
includes the protected oracle, producer, source-preparation and raw exporter.
Changing installed producer code requires a newly reviewed digest; do not
silently replace an existing trusted contract.

## Nine external assertions

1. The real discovery endpoint denies unauthenticated access.
2. A forged token does not become an owner.
3. Fresh, unconfigured tools and catalog entries do not claim authentication,
   protocol verification, readiness, planner availability or execution authority.
4. Unconfigured native Jules remains unavailable.
5. An owner-created randomized disabled model profile appears in discovery,
   preserving its exact identity/model and unavailable state. A hard-coded
   example list cannot satisfy this round trip.
6. An enabled profile pointing to an unverified local endpoint does not become
   inference-ready merely because its configuration was saved.
7. A saved invalid disposable Jules key and allowlist do not prove provider
   authentication or connectivity.

8. Before those seven checks, the controller removes only empty disposable
   model-profile/ChatGPT tables and the shared vault key, then requires
   inventory GET to preserve their absent state. Native Jules tables and keys
   remain intact for cached service prerequisites; their schema/rows/key hashes
   must remain unchanged. This exposes constructors that
   otherwise look read-only after startup or earlier requests initialized them.
   Schema, rows and key digests are compared; unrelated runtime tables are outside
   this assertion's scope.
9. A fixed SQL fixture saves a ready ChatGPT connection selecting `gpt-6-sol`,
   with no credential. The real status API must report that saved state, while
   any unrelated `chatgpt-4o` catalog entry must remain unavailable with reasons
   (omitting that template is also truthful).
   This proves model identity isolation only; saved status is not inference proof.

The state helper is fixed protected stdlib code run through the same pinned
`/usr/local/bin/python3 -I -S` as the HTTP transport, with container identity and
isolation checks before and after. It never imports candidate code and adds no
public seeding API. No fixture stores OAuth tokens or makes a provider call.

The saved Jules assertion sets level five and enables a fake-key adapter **only inside
fresh disposable state**, with no jobs and no external network. No owner
credentials, device state, model weights or production configuration are mounted.
No discovered application is executed, and no model or provider call is needed.

The contract deliberately fixes the current `/integrations/adapters` response
fields. A future API-schema change needs a separately reviewed contract update,
not a permissive fallback that interprets missing data as success.

## Verdict boundary and limitations

All counts originate in the host assertions. A candidate HTTP error carrying
`99 passed` or fabricated XML remains a failure. Source/container/identity
integrity and deadline checks run before and after the suite. Unknown startup,
tampered source or expired review yields no attestation. Observed behavioral
failures can retain the existing signed `FAILED` protocol for bounded failure
handback; they cannot produce a passing acceptance receipt.

The protected producer refuses optimized Python (`-O`/`-OO`) before reading a
configuration or launching a container, because optimization disables the fixed
host assertions. Missing explicit readiness/authentication/protocol/authority
flags are not treated as false; they fail the contract as unknown evidence.

The public-key trust registry, current mission and exact job/patch binding must
still be installed/reviewed through the existing independent-review process.
This change installs no key, registry, grant, mission, service or live adapter.
It does not make catalog inspection into an ACP bridge, installer, authenticated
provider, tested model or production release. Passing these nine checks is
specific readiness evidence only.

## Verification

`python -m pytest tests/test_jules_adapter_oracle.py tests/test_jules_external_review.py tests/test_jules_native_review_worker.py -q`

The controller tests exercise the fixed controller against a real local HTTP boundary
simulator, including false-ready and hard-coded inventory responses. A local isolated
stdlib SQLite test also checks reset, mutation detection and the credential-free
saved-status fixture. They are
controller tests, not Docker or production signature evidence. The protected
supervisor requires a POSIX host; Windows skips in existing tests must not be
reported as successful protected-host execution. A separately authorized Linux
container experiment remains required before installing production reviewer
trust or accepting a live task.
