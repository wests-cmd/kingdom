"""Regression: anonymous callers never reach owner-only Gap Register reads or mutations.

Adapted from the historical autonomous-harness branch after reviewing its
additional tests. No test grants an owner identity or changes production policy.
"""
from fastapi.testclient import TestClient
from backend.main import app
from backend.security.http_auth import require_owner


def test_anonymous_gap_register_routes_reject_all_verbs():
    prior = app.dependency_overrides.pop(require_owner, None)
    try:
        client = TestClient(app)
        cases = [
            ("get", "/system/gap-register", None),
            ("get", "/system/gap-register/autonomous-planning", None),
            ("put", "/system/gap-register/autonomous-planning/evidence",
             {"test_evidence": "not-owner", "status": "verified"}),
            ("post", "/system/gap-register/sync-backlog", None),
        ]
        for verb, path, payload in cases:
            response = getattr(client, verb)(path, json=payload) if payload is not None else getattr(client, verb)(path)
            assert response.status_code in {401, 403}, (verb, path, response.status_code)
    finally:
        if prior is not None:
            app.dependency_overrides[require_owner] = prior
