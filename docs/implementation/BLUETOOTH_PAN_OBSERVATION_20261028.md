# Bluetooth PAN: real OS observations and signed control paths

This extends the opt-in alternate-path control service. It does not create a
second Knight, change grants, pair devices, enable discoverability, install a
privileged helper, bridge a LAN or move execution onto an unverified transport.

The owner-only `GET /peer-paths/bluetooth/status` reads BlueZ ObjectManager on
Linux. It reports powered adapters and currently connected, paired Network1
links on BNEP interfaces. It excludes unrelated device names and does no scan.
Unsupported platforms, missing BlueZ and denied OS permissions return an
explicit unavailable result. An available adapter alone is not an available PAN.

For a configured `bluetooth_pan` probe, the service now requires an OS route to
the destination through that observed BNEP link, and binds the HTTP connection
to its local source IP. It rechecks the route before transmission. A loopback or
Wi-Fi URL cannot be relabeled as Bluetooth by its owner-supplied hint. Existing
pinned node identity, TLS validation, signed heartbeat/reply, current membership
expiry, revocation and durable once-per-probe ledger remain required. Generic
parallel IP tests use two LAN labels, not simulated Bluetooth claims.

The evidence says `bluez_network1_and_os_route_observed`. It is a current OS
observation, not packet capture or proof of radio throughput. Routes can change
while a connection is active. No task or artifact transport is dispatched by
this slice, and a failed or unknown result is not automatically sent again.
Use a new explicit probe key after correcting setup, preserving the old receipt.

## Hardware observation on October 28

Laptop 2 has a powered BlueZ adapter, D8:12:65:D1:3E:C6, and active bluetooth
service. It has no connected PAN link. Its paired phone/device list does not
establish a paired Kingdom Knight. DT1 exposes no `/sys/class/bluetooth` and its
Bluetooth service is inactive. These are live read-only observations, not a
prediction that installing software will provide a radio. The Windows overview
laptop reports an Intel Bluetooth adapter through Windows device inventory;
the Linux BlueZ observer does not claim Windows PAN support.

## Required physical acceptance

1. Supply a working DT1 Bluetooth adapter or select two approved Knights with
   working radios. Use normal OS pairing with owner-confirmed passkey; do not
   auto-trust the device named `net` or the paired phone.
2. Establish an opt-in OS Bluetooth PAN. Keep Wi-Fi active. Verify status exposes
   the paired Network1 interface and route to the intended peer.
3. Configure the already-approved peer's HTTPS PAN endpoint using normal valid
   certificate trust. Both LAN and PAN reuse the current owner-configured mesh
   CA through `mesh_tls()`, or standard trust when no mesh CA is configured.
   CA settings are reread per explicit probe; neither path disables verification.
4. Run separate signed control probes over LAN and PAN concurrently. Retain the
   signed request/reply IDs and OS route observations. Disable PAN, confirm it
   refuses a Wi-Fi fallback labeled Bluetooth, then restore and use a new key.
5. Task routing, artifact chunking, cancellation/failover, exactly-once effects
   and throughput measurements remain separate gates. Passing localhost tests
   is not evidence those physical gates passed.

Tests cover real dual HTTP servers, Ed25519 replies, durable restart dedup,
revocation/expiry, owner boundary and BlueZ/route parsing. No physical Bluetooth
transfer or production installation is claimed by these source tests.

Integration onto main also tests two real concurrent HTTPS servers with a
temporary private CA and actual Ed25519 control replies. The approved CA passes;
an unrelated CA fails before HTTP requests reach the peer. A revoked identity
cannot retrieve a cached successful probe. These tests exercise real TLS and
signed transport, not physical radio transmission.
