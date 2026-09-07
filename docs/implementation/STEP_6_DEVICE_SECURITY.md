# STEP 6 ARCHITECTURE: DEVICE SECURITY & IPC BOUNDARIES

Kingdom enforces strict isolation between desktop IPC channels and local process execution.

## Security Principles
- Context Isolation: Native windows run with `contextIsolation: true` and `nodeIntegration: false`.
- Preload Bridge (`desktop/preload.js`): Exposes sanitized process control functions via `window.kingdomDesktop`.
- Proof-of-Possession Mobile Pairing: Mobile devices must present Ed25519 signature proof during challenge validation.
- Remote Device Revocation: Devices can be revoked instantly from Command Center, invalidating active session tokens.
