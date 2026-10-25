# Swarm authority implementation checkpoint

Status: security core under test, **not connected to production HTTP/RPC or UI**.
This is not a released King/Commander/Ghost Key feature.

## Requested behavior

- One King per Kingdom, crown badge. Offline does not mean absent.
- Commanders have sword badges and authority only over assigned groups. With a King present they require explicit delegation.
- One optional Ghost Key, disabled by default, ghost badge, mobile King authority. The King creates it; a Commander may create it only without a King.
- Ordinary execution controls, exact approvals and OS restrictions remain enforceable.

## Implemented core

`backend/cluster/swarm_authority.py` stores a revisioned authority record in SQLite.
Transactions reject stale edits and preserve a single King and Ghost Key within the record.
King transfer clears previous Commander delegations. Removed group members lose Commander authority.
Ghost secrets use 48 random bytes, are returned once, and only their SHA-256 digest is stored. Revoked keys cannot authorize subsequent transactions; events and status omit secrets.
Group policies are restrictive capability lists and autonomy ceilings, not new tool grants.

`tests/test_swarm_authority.py` exercises these boundaries with an actual temporary SQLite database.
The module is deliberately not used by production authorization yet.

## Remaining integration, in order

1. Bind the registry to the existing owner-selected mesh membership authority. Followers must forward authenticated requests to that authority, never silently establish their own King on a partition. Reject responses from another identity, mismatched request IDs, expired membership or revoked nodes. A changed membership authority needs an explicit migration rather than resurrection of an old role database.
2. Make authoritative group IDs and membership shared first. Current `command_groups` are controller-scoped and use `local` as a controller-relative ID. Normalize real Knight identities before applying cross-Knight authority. Revalidate Commander membership inside the mutation transaction; avoid a stale group snapshot granting rights after a concurrent member move.
3. Add authenticated human controls and signed peer RPC. Actor identity must come from authentication, never JSON/model output. Reject reserved principal names as peer identities. Do not expose the core's internal `owner`/`ghost` actor strings to callers.
4. Enforce permissions and autonomy at **all** execution entry points: local execution, remote dispatch, task polling, management operations, mission workers and direct API routes. A group ceiling must not reduce another group's policy or waive approvals. Pending/in-flight work needs revocation semantics. Default deny if authoritative policy is unavailable.
5. Add Ghost Key setup over HTTPS with no redirects; mobile proof-of-possession and revocation; no conversion into the persistent owner session. Define and enforce the same rights for King and Ghost across relevant endpoints. Only one active key, explicit revoke/replace, no localStorage or secret logging. Record denied operations independently.
6. Add the crown, sword and ghost badges to Swarm, keyboard-accessible setup/revoke/delegate dialogs, readable group scope, and disabled controls with plain-language explanations. No decorative role may imply authority that is not enforced.
7. Integration tests: two controllers share one King; concurrent appointment; cross-group denial; offline King; partition/reconnect; Commander removal race; key rotation/replay; queued-task revocation; browser session separation. Independent reviewer then guarded rollout to DT1 and Laptop 2, followed by other Knights.

The core tests alone do not prove these integration steps or autonomous engineering.
