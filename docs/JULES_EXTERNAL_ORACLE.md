# Jules External Behavioral Test Oracle

## Threat Model & Core Isolation Directives

Importing untrusted candidate Python code directly into `pytest` running on host or controller environments permits candidate code to execute arbitrary instructions during module load or test collection. This can allow candidates to forge test reports (such as generating synthetic JUnit XML output like `<testsuite tests="1"><testcase name="x"/></testsuite>`), print `"1 passed"`, or invoke `os._exit(0)` to abruptly terminate test execution while signaling success to the host controller.

`scripts/jules-external-oracle.py` provides an isolated, trusted host-side behavioral test harness.

### Key Rules & Fences:
1. **Zero Imports**: Candidate modules, tests, `conftest.py`, or pytest plugins are **NEVER** imported into the controller process.
2. **Fixed Container Execution**: Probes execute against disposable API containers driven strictly through `docker exec` using the pinned image interpreter `/usr/local/bin/python3 -I -S` with isolated standard library HTTP probes targeted at the candidate container's loopback interface (`http://127.0.0.1:8012`). Redirects and proxies are disabled.
3. **Strict Container Runtime Checks**:
   - `HostConfig.NetworkMode == "none"`
   - `HostConfig.ReadonlyRootfs == true`
   - `HostConfig.Privileged == false`
   - `HostConfig.CapAdd` is empty or None
   - Non-root container identity (`User != "0"` and `User != "root"`)
   - Read-only workspace source mount (`/workspace`)
   - Exact container Image ID equality matching `sha256:64hex`
   - Forbidden mounts check (no docker socket, secret key paths, or owner state directories)
4. **Host-Owned Assertions**: Candidate responses are treated as untrusted bounded raw bytes (max 64KB). Truncated, malformed, or oversized responses fail immediately. Status assertions, JSON schema validation (`enabled==false`, valid key types), credential redaction scanning, and final test counts are calculated exclusively in the trusted controller process. Missing endpoints return failure (a 404 on required endpoints fails).
5. **Contract Binding**: Contract SHA-256 hashes bind the suite specification, Python probe helper script, and oracle logic version.
6. **Negative-Fence Disclaimer**: The verdict record explicitly notes that passing behavioral assertions proves specific negative security boundaries and fences, but **does not** constitute general autonomous correctness or production deployment readiness.

## Configuration & Contract Schema

Run the controller from trusted operator code, outside the candidate source. Real Docker reviews require a root-owned configuration and ancestor chain with no group/world write access. Keep configuration private (`0600`), particularly the disposable fixture token. The controller is POSIX-only; it is not a production signing service.

```json
{
  "repository": "wests-cmd/kingdom",
  "source": "sources/github/wests-cmd/kingdom",
  "revision": "2c28b5b9dd4595b3a5669467a75c9e7089219733",
  "image": "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "container_name": "kingdom-candidate-probe-instance",
  "deadline_at": 1700000000.0,
  "candidate_patch_sha256": "...",
  "source_directory": "/protected/review/source",
  "source_tree_sha256": "<64 lowercase hex characters>",
  "test_auth_token": "<disposable candidate fixture token only>",
  "api_port": 8012,
  "output_dir": "/protected/review/verdict"
}
```

## Immutable Suite Specification

The initial behavioral suite tests the following endpoints and fences:

1. `api_readiness`: `GET /health/live` -> Expect HTTP 200 OK.
2. `unauthenticated_rejection`: `GET /integrations/jules/settings` -> Expect HTTP 401 or 403.
3. `default_off_jules_settings`: `GET /integrations/jules/settings` (authenticated) -> Expect HTTP 200 OK and strict schema (`enabled` is `False`, `allowed_repositories` list, `allowed_sources` list, `revision` int). Missing routes or malformed JSON fail.
4. `credential_redaction`: `GET /diagnostics/full-scan` (authenticated) -> Expect HTTP 200 OK and verify response body contains no unredacted RSA/SSH keys or vault secret patterns.
5. `unauthenticated_write_rejection`: `POST /vault/kingdom/documents` -> Verify unauthenticated document creation requests are rejected (HTTP 401 or 403).
6. `cancellation_unknown_job`: `GET /integrations/jules/jobs/nonexistent-job-99999` (authenticated) -> Expect HTTP 404 Not Found.
7. `unchanged_authorization`: `GET /integrations/jules/settings` with invalid bearer header -> Expect HTTP 401 or 403.

## Output Verdict Record (`oracle_verdict.json`)

Verdicts are written atomically to `oracle_verdict.json` with `0o600` permissions.

```json
{
  "verdict": "PASSED",
  "disclaimer": "NEGATIVE-FENCE COVERAGE ONLY: This verdict verifies specific security boundaries and behavioral negative fences. It DOES NOT constitute general autonomous correctness, functional completeness, or production deployment readiness.",
  "source_revision": "2c28b5b9dd4595b3a5669467a75c9e7089219733",
  "candidate_patch_sha256": "...",
  "container_image_digest": "sha256:...",
  "contract_sha256": "...",
  "timestamp": 1700000000.0,
  "trusted_test_counts": {
    "total": 7,
    "passed": 7,
    "failed": 0
  },
  "assertion_results": [...]
}
```

## Exact scope and operating requirements

The configuration lives in the protected review directory. Both `source_directory` and `output_dir` must stay inside it; output cannot be inside candidate source. The source tree is hashed before and after probes. Symlinks and special files are rejected. The deadline must be finite, in the future, and at most one hour away.

Use an existing pinned image, numeric non-root UID, fixed API startup command, network `none`, read-only root and source, dropped capabilities, and `no-new-privileges`. Limits are at most 512 MiB RAM, one CPU and 128 PIDs. Only the exact source bind is allowed; do not mount credentials, real owner state, Docker sockets, or additional host directories. Container identity is pinned throughout review. The controller does not create containers or repair their configuration.

`test_auth_token` belongs only to the disposable candidate fixture. Never supply a production owner token or Jules account key. The initial seven checks cover readiness, authorization rejection, disabled settings, diagnostics redaction, and unknown-job handling. They do **not** prove rejection of an unsigned receipt for a known job, functional patch correctness, native failure handback, or complete autonomous execution. Those require separate functional contracts.

No private signing key is used and this output alone cannot authorize acceptance. The independent acceptance consumer needs its separately governed, contract-scoped signed receipt. Inline candidate JUnit remains non-authoritative.

## Provenance and validation

The first Jules candidate failed five independent checks. One bounded correction passed those checks; the operator then hardened source binding, runtime isolation, endpoint accuracy and output containment. These are operator changes, not evidence that Kingdom performed the whole engineering cycle itself.

A real isolated API fixture passed seven external assertions. A forged HTTP test report failed all seven assertions, and a candidate printing success before exiting was rejected. Fixture containers were removed and production reviewer trust was unchanged. Unit tests are in `tests/test_jules_external_oracle.py`; test transport injection is solely a fixture seam and is not selectable through runtime JSON.

Probe execution uses an absolute interpreter path, never the candidate PATH. Writable tmpfs destinations are limited to `/tmp` and `/data`; dynamic loader overrides are rejected. Review found and closed this executable-resolution gap before production trust was enabled. Any controller change changes the contract digest and needs a fresh scoped review.

Further independent review tightened private PID/IPC namespaces, denied host devices and supplementary groups, and required an explicitly enabled no-new-privileges value. Diagnostic scanning checks the known fixture-token canary and four enumerated patterns; it is not exhaustive detection of arbitrary API keys or credentials. Broader redaction proof requires additional independently seeded canaries and schema assertions.

Git `revision` and `candidate_patch_sha256` are **declared input provenance**, not ancestry reconstructed by this script. The verdict marks this explicitly. The controller verifies the mounted source tree against the protected expected tree digest. A future signing bridge must independently reconstruct the exact base plus retained provider patch, verify that resulting tree against this tested tree, and retain that preparation proof. Never sign this diagnostic verdict merely because the two declared hashes look valid.

## Separate exact-source supervisor

`jules-external-review.py` now implements the separate bridge; the diagnostic
script above still cannot sign by itself. The supervisor reconstructs the base
and patch using `jules-source-preparation.py` and the raw Git exporter. It checks
commit, tree and blob object identities, preflights source size, and rejects
external object stores, lazy-fetch configurations, source links and changes
outside an operator-owned exact file list. Export-ignore/export-subst attributes
do not change the tested source.

Install all four supervisor scripts and a bare Git mirror under independently
protected root-owned directories. Use `python3 -I jules-external-review.py
--config /protected/review/config.json`. The private configuration contains the
complete V2 job binding, reviewer identity, private signing-key path, mirror
path, retained patch path, exact allowed paths, installed image digest and a
deadline of at most one hour. No candidate-provided configuration is accepted.

The supervisor creates a fresh network-isolated, read-only, non-root API
container with bounded memory, CPU and processes. Its writable state is private
tmpfs belonging to its non-root UID. Production credentials/state and the signing
key are never mounted. Host-owned assertions produce the signed verdict; a
candidate JUnit file, stdout success string, or caller-supplied verdict is never
an input to the signer. The existing host OpenSSL signs the V2 payload using a
protected Ed25519 seed. Failed behavioral results are signed as failures and
cannot satisfy the passing consumer.

Unique container identity is durably recorded before startup. Unknown startup
outcomes are reconciled by name and unique run label. Restart first cleans up
retained owned containers under an exclusive supervisor lock; unavailable
cleanup blocks a replacement. Every completed run retains preparation, startup
logs and the verdict. Temporary signing-key wrappers are removed. The actual
signing seed remains a separately protected operator credential.

This initial supervisor contract still covers only the seven documented API
fences. It is not adequate functional coverage for unrelated backlog items.
Installing its public reviewer key and contract hash is a separate governed
operation, not something the candidate or planner can do. The DT1 validation
used a disposable key, deleted it afterward and left production trust unchanged.
