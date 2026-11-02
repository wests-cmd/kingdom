"""Verify owner protection on every Gap Register route."""
from backend.system.gap_register_api import router
from backend.security.http_auth import require_owner

def test_gap_register_routes_inherit_owner_dependency():
    assert any(dep.dependency is require_owner for dep in router.dependencies)
    assert {route.path for route in router.routes} >= {
        "/system/gap-register",
        "/system/gap-register/{ident}",
        "/system/gap-register/{ident}/evidence",
        "/system/gap-register/sync-backlog",
    }
