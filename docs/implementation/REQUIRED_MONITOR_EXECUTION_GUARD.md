# Required monitor execution guard: design and acceptance limits

Status: opt-in protocol guard, not an independently isolated monitoring deployment. This candidate does not change any installed policy, grants, OS accounts, units or release version.

## Reproduced seam

The central ZeroTrust authorization path writes audit records before returning approval, but the logger shares Kingdom's process/user. An independent-monitor requirement did not exist there. This patch adds a frozen startup requirement and a signed external receipt check for classified HIGH-risk authorization, including owner level 5. The requirement is not read from model prompts, task metadata, or tool results, and there is no task/API switch to disable it.

```text
trusted runtime startup config
  → authentication and current capability check
  → classify HIGH risk
  → exact-operation digest + fresh nonce to external Unix socket
  → verify pinned Ed25519 signer + exact request + short expiry
  → existing owner approval / standing policy
  → existing audit and execution flow
```

Missing, malformed, oversized, stale, substituted or unsigned receipts deny authorization. Partial or empty startup configuration requires monitoring and fails closed. A monitor failure does not consume an existing exact human approval. A monitor receipt never grants a capability or substitutes for human approval. There is no network fallback and no retry storm. The Unix socket has a 0.5-second I/O timeout and a 0.75-second monotonic total deadline; signed expiry uses wall time and is bounded to five seconds. Receipt size is capped at 4096 bytes. Only a digest, nonce, protocol and expiry are sent, not command arguments or prompts in plaintext.

## Concrete protected deployment design (still to implement and verify)

1. A separately administered supervisor owns its private signing key, audit append storage, notification policy and socket. The worker cannot read the signing key or edit the supervisor's code/configuration. The public key is pinned in an OS-protected runtime launcher configuration.
2. The supervisor validates the exact request, durably appends its security event, and only then signs a `decision=recorded` receipt. It must not expose a general signing service that signs without auditing. The protocol client alone cannot prove durable logging.
3. Run effect-producing workers as restricted OS identities, and protect Kingdom's authorization code, startup requirement and capability broker from worker writes. Merely running the signer in another same-user process does not establish independence. A worker that can rewrite the guard or launch an unguarded process with identical OS privileges can bypass application-level checks.
4. The actual effect broker must require this authorization for each high-risk effect and revalidate current grants/leases. This client is an authorization-time preflight, not a syscall sandbox, continuously supervised process, universal side-effect mediation layer, or cancellation of already-running effects.
5. Add supervisor-offline, key-rotation, worker-tampering and notification-preservation tests using real separated OS principals. These require controlled deployment changes and are not claimed here.

## Protocol / startup configuration

Linux only in this candidate. The trusted launcher supplies `KINGDOM_REQUIRED_MONITOR_SOCKET` and `KINGDOM_REQUIRED_MONITOR_PUBLIC_KEY` (32-byte Ed25519 public key as hex), before constructing ZeroTrust. When neither is set, existing stable authorization behavior is unchanged; this is explicitly **not mandatory monitoring enabled by default**. An installation with no separately protected supervisor is not certified by this feature.

Client sends newline-terminated JSON:

```json
{"protocol":"kingdom.monitor.v1","nonce":"fresh random hex","operation_digest":"sha256","expires_at":1234567890.0}
```

Supervisor returns newline-terminated JSON with `receipt` containing exactly those fields plus `decision: recorded`, and `signature` containing an Ed25519 signature of canonical receipt JSON (sorted keys, compact separators, UTF-8, no NaN). Every authorization attempt gets a fresh nonce; old receipts cannot satisfy a new request. A required monitor on unsupported platforms fails closed.

No private key or production supervisor is generated or installed by this patch. In-memory signing keys/socket servers in tests are fixtures for protocol correctness, not evidence of independent OS enforcement.

## Tests and explicit remaining acceptance gates

The deterministic tests verify exact receipt binding, signature substitution, expiry, frozen/partial startup configuration, model-metadata non-authority, high-risk denial at level 5 and preservation of an approved grant on monitor failure. Linux-only transport tests exercise actual sockets with a valid receipt and wrong nonce/digest/key, oversized/malformed/truncated replies and timeouts. Windows correctly skips those Linux transport cases.

The full `DOOMSDAY_MONITORING_INTEGRITY` acceptance condition remains **unfinished** until an OS-protected supervisor and restricted effect broker are deployed and tested. This patch verifies denial behavior when configured monitoring is unavailable; it does not prove a worker cannot disable monitoring under the current shared-user deployment.
