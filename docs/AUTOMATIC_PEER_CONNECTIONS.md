# Automatic peer connections

The application starts a connection-maintenance service with its backend and stops it on shutdown. Every 15 seconds it reads the persisted registry anew and contacts every approved remote commander with a saved `kingdom_endpoint`. Four connections run concurrently; each attempt has a 35-second deadline. Failed attempts retry on the next sweep. No model request or task execution is involved.

Each connection verifies the pinned identity and exchanges signed heartbeat/inventory messages through the existing replay-protected RPC handler. A success reply without a signed inventory proof is insufficient. Revoked, quarantined, rejected and pending peers are excluded. The service never changes grants, approves identities, or discovers arbitrary network hosts.

The owner-authenticated `GET /federation/connections/status` reports `verified`, `retrying` or `endpoint_required` per eligible peer. Status changes publish `cluster.peer_connection` events. Status is an observation, not authorization or proof of productive work.

## Join once, connect to the approved group

Swarm now includes **Automatic Knight connections**. Choose one computer to keep the owner-approved member list and supply its reachable HTTPS peer endpoint. On a joining Knight, enter its own reachable endpoint, the authority address and a temporary invitation. Approve the incoming request once at the authority. The joining Knight and existing configured members then fetch signed membership rosters and establish their missing reciprocal links automatically. No pair-by-pair invitations are needed within that configured group.

Every participating installation must select the same authority once. Publicly trusted HTTPS certificates work normally; private installations can configure an owner-approved public CA bundle. A certificate or peer announcement alone does not grant membership. Native applications remain loopback-only; the optional peer listener exposes public identity, invitation pairing, heartbeat/inventory and membership RPCs, never owner APIs or execution RPCs. Enable `mesh_enabled` in its server configuration to expose those restricted routes. The older heartbeat-only listener is insufficient for mesh enrollment.

Membership trust is pinned to the selected authority, persisted in SQLite, and applied transactionally. Stale/conflicting generations, wrong authorities, substituted identities and expired rosters are rejected. Local rejection and revocation take precedence. Existing capabilities are preserved; imported peers receive no tool grants. A roster cannot extend a locally shorter temporary membership. Expired temporary memberships are rejected at the signed RPC boundary, even while offline from the authority.

If the authority is offline, existing approved links continue to reconnect. New enrollment and roster changes wait for its return; this feature does not elect an alternative membership authority automatically. Reachability still matters: an offline or firewalled machine cannot be counted as connected. This is activity/inventory connectivity, not shared conversation replication or proof that the whole autonomous coding backlog is executing.

## Verification

`tests/test_mesh_live_join.py` starts three independent real backends with persistent signing keys and three HTTPS peer listeners. It joins two computers through one authority, waits for all six directions without manual sync/reconnect requests, restarts a member, propagates revocation and checks that another member rejects the revoked Knight's signed RPC. The targeted acceptance suite passed 25 tests plus 12 subtests on DT1; receipt `/var/lib/centipede-labs/kingdom-workshop/verification-aac1e3a2c5c0/receipt.xml`. Additional power/temporary-membership and lifecycle checks passed 35 tests; receipt `/var/lib/centipede-labs/kingdom-workshop/verification-068d59989eb7/receipt.xml`. Frontend checks: 28 passed, production build passed.

Rollout and public stable publication are separate from these acceptance tests. Check the owner's dated rollout receipts for the actual installed state on each computer; do not interpret an offline node or a pending native installer as updated and verified.
