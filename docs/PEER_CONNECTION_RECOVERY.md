# Approved peer connection recovery

The peer connection runner starts with the backend lifespan. It observes saved
approved commander identities and endpoints; an unavailable peer remains visible
and can reconnect after its backend or network returns. A liveness timeout does
not remove a permanent owner approval.

Membership-authority refresh, peer reconnects and peer analysis run independently.
One stalled authority, peer or analysis operation therefore does not make the
runner wait for that entire operation before scheduling its next cycle. There is
at most one membership refresh, one reconnect per peer and one analysis operation
per peer in flight. Reconnect network concurrency is capped at four; analysis
concurrency is capped at two. More simultaneously stalled peers can still queue
behind these bounds; this is not a guaranteed heartbeat deadline for any fleet
size or network condition.

The default scheduler interval is 15 seconds. Failed reconnect attempts use a
monotonic 15, 30, 60, then 120-second delay, capped at 120 seconds. Delay starts
when an attempt fails, and the next scheduler cycle can add up to another interval.
A successful verified reconnect clears that peer's backoff. Backoff is transient
process state: restarting the backend permits an immediate attempt using existing
saved trust. It does not create an invitation or renew a grant.

The existing reconnect implementation must verify the pinned remote identity and
signed inventory response before returning success. The runner additionally
re-reads the local identity pin, endpoint, approval state and membership deadline
before reporting verification. Queued analysis rechecks those same values and a
connected state after obtaining its concurrency slot. Revoked, rejected,
quarantined and expired temporary memberships are not renewed or promoted.
Existing analysis execution and capability checks remain authoritative.

Shutdown cancels and drains membership refresh, reconnect and analysis tasks.
Finished child tasks are removed before their exceptions are retrieved, so an
unexpected failed child cannot remain permanently stuck in the task map.

These changes do not configure Wi-Fi, DHCP, gateways, DNS, VPNs or services on
another computer. A disconnected Knight with no working network route needs its
network restored; the UI must not claim it is connected merely because trust is
retained.

## Verification

```sh
python -m pytest tests/test_peer_connections.py tests/test_heartbeat_reconnect_state.py tests/test_mesh_membership.py tests/test_mesh_live_join.py -q
```

The scheduler regressions exercise blocked authority refresh, a stalled peer,
slow analysis, single-flight work, shutdown cancellation, bounded backoff,
concurrent revocation and expiry while analysis is queued. The live mesh test
starts three actual backends with independent databases, signing identities and
TLS listeners, then verifies convergence, restart and revocation. Passing it does
not establish that an owner's physical network or installed fleet is repaired.
