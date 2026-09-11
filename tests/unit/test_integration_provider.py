"""
Tests for ProviderBase and ProviderRegistry.
"""

from backend.integrations.provider import ProviderBase, ProviderRegistry, ProviderHealthStatus
from typing import Dict, Any

class MockTestProvider(ProviderBase):
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        if credentials.get("token") == "valid_token":
            self.health_status = ProviderHealthStatus.HEALTHY
            return True
        self.health_status = ProviderHealthStatus.UNAUTHENTICATED
        return False

    def check_health(self) -> ProviderHealthStatus:
        return self.health_status

    def execute_operation(self, operation: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if self.health_status != ProviderHealthStatus.HEALTHY:
            raise PermissionError("Provider not healthy")
        self.metrics.total_calls += 1
        self.metrics.successful_calls += 1
        return {"status": "ok", "op": operation, "params": params}

def test_provider_registration_and_auth():
    registry = ProviderRegistry()
    provider = MockTestProvider("org.kingdom.test", "Test Provider", "1.0.0")
    registry.register_provider(provider)

    assert registry.get_provider("org.kingdom.test") == provider
    assert provider.health_status == ProviderHealthStatus.UNAUTHENTICATED

    # Authenticate
    assert provider.authenticate({"token": "valid_token"}) is True
    assert provider.health_status == ProviderHealthStatus.HEALTHY

    # Execute
    res = provider.execute_operation("echo", {"msg": "hello"}, {})
    assert res["status"] == "ok"
    assert provider.metrics.total_calls == 1

def test_provider_revocation():
    registry = ProviderRegistry()
    provider = MockTestProvider("org.kingdom.test2", "Test Provider 2", "1.0.0")
    registry.register_provider(provider)
    provider.authenticate({"token": "valid_token"})

    registry.revoke_provider("org.kingdom.test2")
    assert provider.health_status == ProviderHealthStatus.REVOKED
