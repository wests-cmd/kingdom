# Distributed Authority Model Architecture

## Principle: Single Source of Execution Authority

Kingdom v40.2 distributes computation and capability execution across nodes without distributing security authority ambiguously.

```text
COMMANDER (KG-MASTER-01 Single Source of Authority)
 ↓
CAPABILITY ROUTER (CapabilityRouter Policy & Locality Selection)
 ↓
TASK LEASE MANAGER (TaskLeaseManager Monotonic Fencing Token)
 ↓
SIGNED RPC TRANSPORT (RPCSecureTransport Anti-Replay & Ed25519 Signatures)
 ↓
KNIGHT NODE (Execution Worker - Evaluates Lease & Fencing Token)
```

---

## Authority Distribution Rules

1. **Identity Ownership:** The Commander (`KingdomIdentity`) owns root node identity authorization and capability granting.
2. **Capability Grants:** Nodes possess only granted capabilities (`granted_capabilities`). Declaring additional capabilities in discovery payloads does not grant execution authority.
3. **Lease Fencing:** Monotonically increasing fencing tokens (`TaskLeaseManager`) prevent stale or disconnected workers from executing tasks after leases expire or are reassigned.
4. **Data Locality:** Local-only data policies (`local_only`) prohibit sensitive data transfers across network boundaries regardless of remote compute availability.
5. **Fail-Closed Partitioning:** During network partition timeouts, isolated nodes transition to `DISCONNECTED` state and capability execution fails closed.
