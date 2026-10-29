# Opt-in alternate IP control paths

This slice sends real authenticated control traffic over an explicitly selected
additional IP endpoint. Bluetooth PAN can supply that IP interface; Kingdom does
not pair radios, create a PAN bridge, change routes/firewalls, grant capabilities
or infer radio availability. Existing Wi-Fi/Ethernet endpoints remain unchanged.
There are no paths until the authenticated owner configures them.

## Implemented protocol

An owner configures up to two named paths for one existing approved pinned
Kingdom peer using `PUT /peer-paths/{peer}` with `expected_revision` and `paths`:

```json
{"expected_revision":0,"paths":[
  {"name":"wifi","endpoint":"https://192.168.1.20:8000","transport_hint":"lan"},
  {"name":"pan","endpoint":"https://192.168.44.2:8000","transport_hint":"bluetooth_pan"}
]}
```

These are examples, not discovered or installed endpoints. Use a working normal
trusted TLS certificate valid for each address. Explicit loopback HTTP tunnels
are supported; cleartext non-loopback requests, DNS hostnames, public/link-local
addresses, credentials, redirects and arbitrary URL paths are rejected. Proxy
environment settings are not used. An untrusted peer cannot advertise a new path.

The owner can request up to eight independent probes in one call:

```json
{"probes":[{"key":"check-wifi-001","path":"wifi"},
           {"key":"check-pan-001","path":"pan"}]}
```

Send that body to `POST /peer-paths/{peer}/probe`. A maximum of two exchanges run
concurrently per service process. Each fetches the public identity at the fixed
path, compares the existing pinned key/fingerprint, rechecks owner configuration
and revocation, sends one signed heartbeat through existing `/nodes/rpc`, and
requires a signed inventory response bound to that exact request ID. Receiving
nodes now include that request ID in the signed heartbeat response. Older peers
without the binding remain unverified; no weaker fallback is accepted.

Each active exchange has a five-second total deadline around OS observations,
TLS and both HTTP streams, in addition to HTTP inactivity limits. A peer cannot
retain a slot indefinitely by slowly dripping bytes. Expiry before sending RPC
records `not_sent`; expiry after sending retains `outcome_unknown`. The durable
probe key is not retransmitted in either case. Queue waiting and local SQLite
receipt persistence are separate from this OS/network deadline.

RPC signatures, current peer state, durable replay protection and existing
remote heartbeat policy remain authoritative. A heartbeat cannot execute work.
This endpoint accepts no task, management operation, tool payload or new grants.

## No uncertain retries

Before transmission, SQLite atomically reserves `(peer, owner key)` bound to
the exact owner path configuration. Concurrent duplicates and restarted service
instances do not resend the key. A completed key returns its historical result
with its original observation timestamp. A lost reply, cancelled request or
crash remains `outcome_unknown`; a new key is a new owner-requested control probe,
not a replay of the original request. Keys cannot migrate to another path or
configuration. The ledger stops accepting new keys at 10,000 records instead of
deleting deduplication history. Owner maintenance/retention tooling is future work.

Configured transport hints are labelled `owner_configured_not_radio_observed`.
The October 28 extension requires a real paired BlueZ PAN link, matching OS route
and bound source IP before probing a `bluetooth_pan` path. Its receipt labels
that evidence `bluez_network1_and_os_route_observed`; this is not packet capture
or radio-throughput proof. A successful exchange records elapsed time and signed
request/response IDs. It cannot mark a task complete or renew tool authority.
Previously verified probes are historical evidence, not continuous health.

## Tested scope and remaining work

Tests use two actual loopback HTTP servers, real Ed25519 identities, real SQLite
RPC replay and sender deduplication ledgers, and overlapping signed requests.
They test lost replies, concurrent duplicate keys, restart, revocation, changed
configuration, substituted request receipts, redirect rejection, owner-only
routes and exclusion of execution payloads. These are network protocol tests,
not a physical Bluetooth demonstration or a task-throughput benchmark.

The owner-only Bluetooth status endpoint and OS route checks are implemented in
the October 28 extension. Still required: owner pairing/PAN setup;
two-Knight on-radio verification with Wi-Fi active;
Swarm path visibility; explicit policy for small chat/data requests; bounded file
chunks; and end-to-end execution receipt deduplication before routing tasks or
retrying side effects across paths. There is no bandwidth aggregation, automatic
failover of work, privileged network helper or general parallel task support.

The existing transport-abstraction placeholder classes are not used as evidence
or as the network implementation of this feature.
