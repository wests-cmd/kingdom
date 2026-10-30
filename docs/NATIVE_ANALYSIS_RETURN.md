# Native analysis over one reachable connection

Source supports controller-initiated native analysis over an existing approved
peer connection. The worker returns a signed result in the same HTTP exchange;
it does not need to initiate a second connection to the controller.

```text
controller: authorize and claim one exact task/lease
  signed native_analysis_execute -> approved worker
  worker: current authority/power/capacity check -> durable claim -> literal analysis
  signed task_result <- same HTTP response
controller: signature + correlation + current grant + active lease + independent recomputation
```

The only tools supported are `text.analyze@1.0.0` and
`code.python.analyze@1.0.0`, with bounded literal text and existing `compute`
permission. Python analysis parses syntax; it does not execute Python or its
tests. This is not a general repository coding, file-transfer or model path.

## Compatibility and authority

Updated peers advertise `native_analysis_return: true` in signed heartbeat and
inventory proofs. The controller uses the new path only after that authenticated
feature report. Older peers retain their existing worker-poll path. Both peers
need the source update before the asymmetric-link repair can be demonstrated.

Dispatch still uses the runtime's normal owner policy, approval and atomic lease
claim. The receiving Knight independently checks its current local runtime/coder
compute authority, approved peer identity, fresh health report, temporary
membership expiry, capacity and power. Capability reports do not grant authority.

Results must match the exact request ID, worker identity, task ID, lease ID and
fencing generation. The normal cluster result handler verifies the worker's
signature and current grant/lease, independently recomputes analysis and only
then completes the task. Revocation, reassignment or emergency stop can reject a
late result even if the worker retained a valid historical result.

## Recovery and retention

An active lease whose HTTP response was lost can be retried with a new signed
request ID. The worker reuses its durable result; it does not recompute it.
Updated worker-poll and controller-offer paths share that execution claim.
Concurrent or interrupted worker execution stays held, with no automatic replay
of an unresolved claim. Lease expiry/reassignment remains the controller's
existing recovery responsibility.

The worker retains at most 1,000 task claim/high-water records. A full ledger
holds new work for retention review rather than dropping replay evidence.
An old worker version did not maintain the new in-flight claim: drain legacy
analysis work before upgrading it. The new source does not establish a migration
guarantee for work already executing under an older version.

## Verification

```bash
python -m pytest tests/test_peer_analysis_return.py tests/test_native_peer_analysis.py tests/test_peer_analysis_relay.py tests/test_peer_connections.py tests/test_federation_power.py tests/test_autonomy_acceptance.py tests/test_execution_policy.py -q
```

The same-connection tests exercise real RuntimeEngine dispatch, durable leases,
signed RPC handling, literal execution and independent controller verification.
They inject a lost HTTP response, then forbid a second execution, and verify the
retry still completes. Negative cases cover grant revocation, expired/revoked
leases, changed task inputs, restricted tools, signature tampering and worker
interruption. Identity routing and local load are test plumbing; these tests do
not prove physical DT1/Laptop 2 deployment or Bluetooth transport.

Installed source, both signed feature reports and one independently verified
physical task are separate rollout gates. No routes, tunnels, grants, pairing or
expired authorization windows are created by this path.
