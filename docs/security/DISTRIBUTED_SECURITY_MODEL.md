# Distributed Security Model

## Non-Negotiable Security Principles

1. **Single Source of Security Authority:** The Kingdom Commander owns root capability granting. Local node discovery declarations do not grant permissions.
2. **Mutual Cryptographic Authentication:** All distributed RPC messages use Ed25519 signatures and message ID tracking for replay attack prevention (`RPCSecureTransport`).
3. **Lease Fencing:** Monotonic fencing tokens prevent stale workers from executing tasks after lease reassignment.
4. **Data Locality Policy:** Sensitive local data cannot be transferred across node boundaries when marked `local_only`.
5. **Authoritative Revocation Propagation:** Revoked nodes or capabilities fail closed immediately across the cluster. Reconnection attempts by revoked nodes are rejected.
