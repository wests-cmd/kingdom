# Automatic peer connections

The application starts a connection-maintenance service with its backend and stops it on shutdown. Every 15 seconds it reads the persisted registry anew and contacts every approved remote commander with a saved `kingdom_endpoint`. Four connections run concurrently; each attempt has a 35-second deadline. Failed attempts retry on the next sweep. No model request or task execution is involved.

Each connection verifies the pinned identity and exchanges signed heartbeat/inventory messages through the existing replay-protected RPC handler. A success reply without a signed inventory proof is insufficient. Revoked, quarantined, rejected and pending peers are excluded. The service never changes grants, approves identities, or discovers arbitrary network hosts.

The owner-authenticated `GET /federation/connections/status` reports `verified`, `retrying` or `endpoint_required` per eligible peer. Status changes publish `cluster.peer_connection` events. Status is an observation, not authorization or proof of productive work.

## Remaining work for automatic all-to-all joining

This is connection maintenance, not completed group enrollment. A new Knight still needs owner-approved identity records and reachable endpoints on every other installation. Do not substitute trust in an advertiser for owner approval. The next implementation must distribute an owner-authorized, Kingdom-scoped membership roster with pinned identities, expiration/revocation handling, and endpoint trust configuration; reconcile missing pairs without copying tool grants. Temporary container membership must retain its task-bound lifetime. Existing TLS heartbeat-only companion listeners are not full federation endpoints and cannot be registered as such.

Acceptance: join a fresh Knight once, establish all missing reciprocal links without manual pair-by-pair setup, restart it, revoke it, and demonstrate rejection on every remaining member. Test partitions and competing roster updates before release.

## Verification

Three focused async tests cover detecting new approved peers, revocation, unapproved exclusion, missing endpoints, retry and lifecycle idempotency. Together with heartbeat transport tests: 7 tests and 12 subtests passed in DT1's isolated workshop; receipt `/var/lib/centipede-labs/kingdom-workshop/verification-4746c3a53f46/receipt.xml`.

This change has not been deployed to the four running installations and is not a stable release.
