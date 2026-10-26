# Jules External Behavioral Test Oracle

## Threat Model & Core Isolation Directives

Importing untrusted candidate Python code directly into `pytest` running on host or controller environments permits candidate code to execute arbitrary instructions during module load or test collection. This can allow candidates to forge test reports (such as generating synthetic JUnit XML output like `<testsuite tests="1"><testcase name="x"/></testsuite>`), print `"1 passed"`, or invoke `os._exit(0)` to abruptly terminate test execution while signaling success to the host controller.

`scripts/jules-external-oracle.py` provides an isolated, trusted host-side behavioral test harness.

### Key Rules & Fences:
1. **Zero Imports**: Candidate modules, tests, `conftest.py`, or pytest plugins are **NEVER** imported into the controller process.
2. **Fixed Container Execution**: Probes execute against disposable API containers driven strictly through `docker exec` using `python3 -I -S` with isolated standard library HTTP probes targeted at the candidate container's loopback interface (`http://127.0.0.1:8012`). Redirects and proxies are disabled.
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

Configurations must be owned by the running process UID and possess strict permissions (`0o600`).

```json
{
  "repository": "wests-cmd/kingdom",
  "source": "sources/github/wests-cmd/kingdom",
  "revision": "2c28b5b9dd4595b3a5669467a75c9e7089219733",
  "image": "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "container_name": "kingdom-candidate-probe-instance",
  "deadline_at": 1700000000.0,
  "candidate_patch_sha256": "...",
  "output_dir": "/protected/oracle_out"
}
```

## Immutable Suite Specification

The initial behavioral suite tests the following endpoints and fences:

1. `api_readiness`: `GET /health/live` -> Expect HTTP 200 OK.
2. `unauthenticated_rejection`: `GET /vault/kingdom/documents` -> Expect HTTP 401 or 403.
3. `default_off_jules_settings`: `GET /integrations/jules/settings` (authenticated) -> Expect HTTP 200 OK and strict schema (`enabled` is `False`, `allowed_repositories` list, `allowed_sources` list, `revision` int). Missing routes or malformed JSON fail.
4. `credential_redaction`: `GET /diagnostics/full-scan` (authenticated) -> Expect HTTP 200 OK and verify response body contains no unredacted RSA/SSH keys or vault secret patterns.
5. `no_unsigned_acceptance`: `POST /vault/kingdom/documents` -> Verify unsigned document creation requests with source labels are rejected (HTTP 401, 403, 422).
6. `cancellation_unknown_job`: `GET /integrations/jules/jobs/nonexistent-job-99999` (authenticated) -> Expect HTTP 404 Not Found.
7. `unchanged_authorization`: `GET /vault/kingdom/documents` with invalid bearer header -> Expect HTTP 401 or 403.

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
