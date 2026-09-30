# Kingdom Profiles & API Capability Catalog Architecture

This document describes the design, data domain, catalog sync, provider verification, and security boundaries for Kingdom's **Profiles + Capability Catalog** system.

---

## 1. Architectural Overview

Kingdom translates human intent into structured execution without forcing nontechnical users to configure APIs, keys, models, or internal Knights.

```text
USER / CENTIPEDE
      ↓
REQUEST
      ↓
ACTIVE USER PROFILE (e.g. Researcher)
      ↓
CAPABILITY RESOLUTION (e.g. research, web_search)
      ↓
API PROVIDER CATALOG (Verified available providers)
      ↓
ZERO-TRUST AUTHORIZATION (Policy evaluation)
      ↓
TASK CREATION & SCHEDULER
      ↓
WORKLOAD BALANCER & KNIGHT EXECUTION
      ↓
VERIFICATION, PERSISTENCE & AUDIT LOG
```

---

## 2. Core Domain Models

### Profiles
A human-friendly persona (e.g. *General Assistant*, *Researcher*, *Student*, *Developer*, *Business*, *Reseller*, *Market Research*, *Finance*, *News*, *Travel*, *Creator*, *Community Moderator*).

### Capabilities
Standardized execution vocabulary (e.g., `web_search`, `research`, `news_search`, `product_search`, `product_research`, `price_comparison`, `market_research`, `financial_data`, `weather_lookup`, `geolocation`, `travel_information`, `image_search`, `image_generation`, `book_search`, `science_data`, `translation`, `text_analysis`, `code_analysis`, `community_moderation`).

### API Providers & Mappings
Catalog records storing provider metadata (homepage, docs, HTTPS support, auth requirements, CORS, free access level, verification status).

---

## 3. Synchronization & Verification

1. **Public APIs Adapter:** Isolated, read-only adapter fetching from `https://api.publicapis.org` (configurable via `KINGDOM_API_CATALOG_PUBLIC_APIS_URL`).
2. **Catalog Sync:** Idempotent service recording entries seen, added, and updated in `api_catalog_syncs`.
3. **Provider Verification:** Non-destructive reachability checks storing evidence in `api_verifications` and updating verification status.

---

## 4. Security Boundary Rules

1. **Profile != Permission:** Profiles select active capabilities, but do not grant execution authorization.
2. **Catalog Entry != Permission:** The presence of an API in the catalog does not allow arbitrary execution.
3. **ZeroTrust Authority:** All tasks and side effects remain strictly policy-gated and approval-checked by Kingdom's ZeroTrust engine.
4. **Credential Protection:** API credentials and keys are never logged or stored in plaintext.
