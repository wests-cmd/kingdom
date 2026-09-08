# STEP 6 DEVICE & NATIVE APP TEST PLAN

## Automated Integration Test Suites
1. `tests/test_api.py`: Tests REST endpoints, `/health/ready`, `/system/check`, and `/api/system/version`.
2. `tests/test_runtime_core.py`: Tests async runtime engine, task execution, and deterministic polling.
3. `tests/unit/test_cluster_federation.py`: Tests multi-node cluster federation, Ed25519 pairing, signed RPC transport, and cross-Kingdom isolation.
4. `tests/unit/test_mobile_knowledge_skills_governance.py`: Tests mobile challenge pairing, document ingestion, source-of-truth conflict detection, skill teaching/promotion, and governed financial execution denial.
5. `tests/unit/test_native_desktop_mobile_e2e.py`: Tests end-to-end desktop launcher lifecycle, mobile QR pairing, proof-of-possession verification, target Kingdom identity binding on reconnection, and post-revocation denial.

All 55 test cases in the Kingdom test suite pass cleanly.
