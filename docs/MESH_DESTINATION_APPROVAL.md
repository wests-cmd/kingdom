# Mesh bootstrap destination approval

Fresh mesh enrollment requires an authenticated owner's explicit local destination
confirmation before the service makes any network request. An invitation signature
proves possession of its advertised identity key; it does not grant network access,
tool capabilities or permission to run tasks.

1. Obtain a new full invitation from the updated authority's owner-only
   `POST /nodes/invitation`. It includes `invitation_signature`, covering a
   domain-separated canonical JSON encoding of code, authority ID, key, fingerprint,
   creation and expiration. Legacy unsigned invitations must be recreated; no
   unsigned fallback is performed for bootstrap.
2. Review the exact authority origin and fingerprint out of band. Explicitly
   confirm through owner-only `POST /federation/mesh/destinations` with
   `{ "authority_endpoint": "https://your-approved-peer:8443", "invitation": { ... } }`.
   This operation performs no network requests and grants no tools. Its response
   includes `approval_id`, normalized `authority_endpoint`, `authority_id`,
   `fingerprint` and `expires_at`.
3. Submit the same signed invitation and authority origin to
   `POST /federation/mesh/join`, adding `destination_approval_id` from that response,
   the local endpoint and any reviewed CA bundle.

Only one fresh destination approval is retained at a time. It lasts at most five
minutes and never longer than the invitation. Replacement invalidates the previous
approval. It is reserved transactionally before the pairing POST, after the identity
GET succeeds. A failed GET can be retried within the original window. A lost POST
acknowledgment cannot automatically reuse it; inspect the remote state before an
owner explicitly confirms another attempt.

Previously approved peer identities may use their exact saved origin without a
new destination approval. Their key/fingerprint/state must still match; the join
invitation must be current and signed. Existing signed mesh synchronization and
ordinary reconnection do not require this fresh-bootstrap approval. Revocation,
changed pins and expiration are rechecked after the identity GET, before POST.
After the remote POST, local registration uses an authoritative SQLite transaction:
it inserts only a still-absent authority and never overwrites a concurrent restricted
state, replacement identity, endpoint or existing grants. A removed previously
approved authority is not automatically recreated. Conflicts return HTTP 409 with
a warning that remote pairing may have succeeded; reconcile rather than replay.

Private LAN, tailnet and explicit loopback origins are supported under these
owner pins; they are not granted blanket reachability. Remote URLs require HTTPS,
with certificate validation and optional owner CA trust retained. Redirects and
environment proxies are disabled, and only fixed identity/pair paths are fetched.
The hostname/origin is the owner's network policy: this does not independently
attest DNS ownership or make an untrusted owner's selected server safe.

The remote owner still approves the joining Knight. Membership does not add tool
grants. Frontend/API callers must present confirmation as an explicit owner action,
not automatically approve any model- or document-supplied URL.
