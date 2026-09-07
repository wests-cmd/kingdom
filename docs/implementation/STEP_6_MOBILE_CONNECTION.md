# STEP 6 ARCHITECTURE: MOBILE ↔ DESKTOP CONNECTION ARCHITECTURE

Kingdom Mobile (`apps/mobile/`) acts as a bounded companion interface communicating with the main desktop/server Kingdom Runtime.

## Shared State Architecture
```
          ┌─────────────────────┐
          │    Kingdom Core     │
          │  (data/kingdom.db)  │
          │                     │
          │ Commander           │
          │ Swarm & Memory      │
          │ Security & Governance│
          └──────────┬──────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
    Native Desktop       Kingdom Mobile
       Client                Client
```
- Desktop and Mobile share the same persistent SQLite database (`data/kingdom.db`), task queue, memory stores, and Zero-Trust capability firewall.
- Actions initiated on phone (voice, photo upload, skill teaching) are processed by local Commander/Knights and reflected on desktop in real time.
