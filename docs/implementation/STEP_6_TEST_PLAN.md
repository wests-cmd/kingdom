# STEP 6 NATIVE DESKTOP & MOBILE TEST PLAN

## Automated Test Suites
1. `tests/test_api.py`: Tests REST endpoints, `/health/ready`, `/system/check`, and system version API.
2. `tests/unit/test_cluster_federation.py`: Tests multi-node federation, Ed25519 pairing, signed RPC transport, and cross-Kingdom isolation.
3. `tests/unit/test_mobile_knowledge_skills_governance.py`: Tests mobile challenge pairing, document ingestion, source-of-truth conflict detection, skill teaching/promotion, and governed financial execution denial.

All 54 test cases in the Kingdom test suite pass cleanly.
