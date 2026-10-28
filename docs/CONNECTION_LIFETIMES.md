# Membership, availability and temporary work sessions

Permanent approved Knights retain their pinned identity, pairing, permissions and
history across sleep, network loss and restart. An offline heartbeat stops new
placement on that peer; it does not revoke trust or require pairing again. A
fresh authenticated exchange restores availability. Explicit revocation,
quarantine and identity changes still require their existing controls. Short-lived
RPC proofs, invitations and execution leases must retain their security expiry;
these are separate from permanent membership.

Current implementation: permanent registrations survive heartbeat timeout and
repository reload. A regression test covers unchanged key, grants and endpoint,
then reconnection without another invitation. Liveness must never be faked by
disabling heartbeat checks or setting disconnected nodes to connected locally.

## Temporary container sessions — required, not implemented by this document

The owner wants explicit temporary connections for task environments. Containers
are child workloads of their host Knight, not extra physical Knight identities.

Required lifecycle:

1. Allocate a new durable session ID, tied to host, workload instance, task and
   attempt. Reusing a container for another assignment creates a new session.
2. Bind only the task's existing approved capabilities. Creating a session cannot
   grant authority, inherit unrelated permissions or extend an expired grant.
3. Retain the connection while executing, independently checking and repairing.
   A worker's completion claim alone cannot close it as passed.
4. Close the session after required independent checks pass. Record the checked
   artifact hash, verifier identity and acceptance receipt. Reject replay or
   further execution using the closed session. Keep its history.
5. Failure remains failed/repairable with bounded retries and checkpoints; it
   cannot be marked passed. Cancellation, revocation and hard resource limits
   can close a session early, with the actual reason retained.
6. A new or reused environment obtains a fresh session. Old messages, leases and
   acceptance receipts cannot authorize the new assignment.

Acceptance still required: real task to container, verification failure and
repair, passing independent checks, automatic closure, reuse with a different
session, replay rejection, host restart recovery and owner-visible history.
No claim that this container lifecycle is implemented or deployed yet.
