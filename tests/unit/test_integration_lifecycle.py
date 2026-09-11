"""
Tests for IntegrationLifecycleEngine state transitions and terminal revocation.
"""

import pytest
from backend.integrations.lifecycle import IntegrationLifecycleEngine
from backend.integrations.manifest import IntegrationLifecycleState
from backend.integrations.provider import ProviderRegistry, ProviderBase, ProviderHealthStatus

class DummyProvider(ProviderBase):
    def authenticate(self, credentials): return True
    def check_health(self): return self.health_status
    def execute_operation(self, op, p, c): return {}

def test_integration_lifecycle_valid_transitions():
    registry = ProviderRegistry()
    provider = DummyProvider("org.kingdom.github", "GitHub", "1.0.0")
    registry.register_provider(provider)

    engine = IntegrationLifecycleEngine(registry)
    assert engine.get_state("org.kingdom.github") == IntegrationLifecycleState.DISCOVERED

    # Walk lifecycle
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.VALIDATED)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.INSTALLED)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.AUTHENTICATED)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.VERIFIED)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.ENABLED)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.HEALTHY)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.ACTIVE)

    assert engine.get_state("org.kingdom.github") == IntegrationLifecycleState.ACTIVE

def test_invalid_lifecycle_transition_rejection():
    registry = ProviderRegistry()
    engine = IntegrationLifecycleEngine(registry)

    with pytest.raises(ValueError):
        engine.transition_state("org.kingdom.github", IntegrationLifecycleState.ACTIVE)

def test_integration_revocation():
    registry = ProviderRegistry()
    provider = DummyProvider("org.kingdom.github", "GitHub", "1.0.0")
    registry.register_provider(provider)

    engine = IntegrationLifecycleEngine(registry)
    engine.transition_state("org.kingdom.github", IntegrationLifecycleState.VALIDATED)

    engine.revoke_integration("org.kingdom.github", "Security audit failure")
    assert engine.get_state("org.kingdom.github") == IntegrationLifecycleState.REVOKED
    assert provider.health_status == ProviderHealthStatus.REVOKED
