"""
Unit & Integration Tests for Profiles, Capabilities, API Catalog, Sync, Verification, and Capability Resolution.
"""

import pytest
import time
from backend.catalog.repository import catalog_repo, CatalogRepository
from backend.catalog.sources.public_apis import PublicApisSourceAdapter, normalize_auth, normalize_free_access
from backend.catalog.sync_service import CatalogSyncService
from backend.catalog.verification_service import VerificationService
from backend.catalog.resolver import CapabilityResolver
from backend.security.zero_trust import ZeroTrust


def test_system_profiles_and_capabilities_seeded():
    profiles = catalog_repo.list_profiles()
    assert len(profiles) >= 12
    slugs = {p["slug"] for p in profiles}
    assert "general_assistant" in slugs
    assert "researcher" in slugs
    assert "developer" in slugs
    assert "business" in slugs
    assert "reseller_buyer_seller" in slugs
    assert "community_moderator" in slugs

    capabilities = catalog_repo.list_capabilities()
    assert len(capabilities) >= 19
    cap_slugs = {c["slug"] for c in capabilities}
    assert "web_search" in cap_slugs
    assert "research" in cap_slugs
    assert "financial_data" in cap_slugs
    assert "product_search" in cap_slugs


def test_active_user_profile_switching():
    active = catalog_repo.get_active_user_profile("default_user")
    assert active is not None

    # Switch active profile
    updated = catalog_repo.set_active_user_profile("prof-researcher", user_id="default_user")
    assert updated["profile_id"] == "prof-researcher"
    assert updated["profile_slug"] == "researcher"

    # Reset back to general assistant
    catalog_repo.set_active_user_profile("prof-general_assistant", user_id="default_user")


def test_public_apis_normalization():
    assert normalize_auth("ApiKey") == "api_key"
    assert normalize_auth("OAuth") == "oauth"
    assert normalize_auth(None) == "none"
    assert normalize_free_access("none", True) == "free"
    assert normalize_free_access("api_key", True) == "credentials_required"


def test_catalog_sync_idempotency_and_linking(monkeypatch):
    class MockAdapter:
        def fetch_entries(self):
            return [
                {
                    "slug": "test-news-api",
                    "name": "Test News API",
                    "description": "Live headlines and news aggregation",
                    "homepage_url": "https://news.example.com",
                    "documentation_url": "https://news.example.com/docs",
                    "source": "public_apis",
                    "category": "News",
                    "auth_type": "none",
                    "https_supported": True,
                    "cors_support": "yes",
                    "free_access": "free",
                    "metadata_json": {}
                }
            ]

    sync_service = CatalogSyncService(repository=catalog_repo, adapter=MockAdapter())
    res1 = sync_service.sync_public_apis()
    assert res1["status"] == "completed"
    assert res1["entries_seen"] == 1

    # Second sync (idempotency check)
    res2 = sync_service.sync_public_apis()
    assert res2["status"] == "completed"
    assert res2["entries_seen"] == 1

    provider = catalog_repo.get_api_provider("test-news-api")
    assert provider is not None
    assert provider["name"] == "Test News API"
    cap_slugs = [c["slug"] for c in provider.get("capabilities", [])]
    assert "news_search" in cap_slugs


def test_provider_verification():
    verif_service = VerificationService(repository=catalog_repo)
    provider = catalog_repo.get_api_provider("test-news-api")
    assert provider is not None

    res = verif_service.verify_provider(provider["id"])
    assert "verification_status" in res
    assert "reachable" in res


def test_capability_resolver_engine():
    resolver = CapabilityResolver(repository=catalog_repo)
    resolution = resolver.resolve_profile_capabilities(user_id="default_user")

    assert "active_profile" in resolution
    assert "capabilities" in resolution
    assert resolution["resolved_capabilities_count"] > 0


def test_doomsday_source_offline_failure_handling():
    class OfflineAdapter:
        def fetch_entries(self):
            return []

    sync_service = CatalogSyncService(repository=catalog_repo, adapter=OfflineAdapter())
    res = sync_service.sync_public_apis()
    assert res["status"] == "completed"
    assert res["entries_seen"] == 0


def test_security_boundary_profile_does_not_grant_permission():
    security = ZeroTrust()
    auth_res = security.authorize(
        actor_id="test_actor",
        capability="admin.delete_all",
        operation="Unauthorized Administrative Destructive Operation"
    )
    assert auth_res["authorized"] is False
