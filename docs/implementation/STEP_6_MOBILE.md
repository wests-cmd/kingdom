# STEP 6 ARCHITECTURE: MOBILE GATEWAY & PHONE PAIRING

The Mobile Gateway (`apps/mobile/`) serves as a bounded orchestration interface for normal users.

## Phone Pairing Protocol Flow
1. Commander generates a short-lived, single-use pairing challenge code (`POST /mobile/challenge`).
2. Mobile app scans/enters code and returns proof-of-possession signature signed by device keypair (`POST /mobile/pair`).
3. Commander verifies signature and registers phone in `PENDING_APPROVAL` state.
4. Human operator approves device (`POST /mobile/{id}/approve`).
5. Mobile device gains scoped authority for bounded voice/text/photo interactions.

## Remote Revocation & Session Security
- Mobile devices do not hold Commander private identity material.
- Human operators can instantly revoke mobile device authority via `POST /mobile/{id}/revoke`.
