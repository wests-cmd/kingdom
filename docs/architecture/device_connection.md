# KINGDOM ARCHITECTURE: DEVICE CONNECTION & MOBILE PAIRING PROTOCOL

Kingdom Mobile (`apps/mobile/`) communicates with Kingdom Core over an authenticated, cryptographically paired session.

## Device Pairing Sequence
1. Desktop Commander generates single-use pairing challenge code (`POST /mobile/challenge`).
2. Mobile device presents challenge code and proof-of-possession Ed25519 signature (`POST /mobile/pair`).
3. Commander registers phone in `PENDING_APPROVAL` state.
4. Human operator approves phone from Command Center Devices view (`POST /mobile/{id}/approve`).
5. Scoped mobile session token issued for bounded voice, upload, and approval interactions.

## Security Controls
- Mobile devices cannot self-grant capabilities.
- Device revocation (`POST /mobile/{id}/revoke`) immediately invalidates session tokens.
- Reconnection attempts check target Kingdom identity binding to prevent cross-Kingdom leaks.
