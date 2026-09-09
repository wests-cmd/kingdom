"""
Kingdom Integration Lifecycle & Revocation State Machine.
Manages strict transition rules across DISCOVERED -> ACTIVE -> REVOKED/QUARANTINED.
"""

from typing import Dict, Any, Optional, List
from backend.integrations.manifest import IntegrationLifecycleState
from backend.integrations.provider import ProviderRegistry, ProviderHealthStatus

class IntegrationLifecycleEngine:
    ALLOWED_TRANSITIONS = {
        IntegrationLifecycleState.DISCOVERED: [IntegrationLifecycleState.VALIDATED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.VALIDATED: [IntegrationLifecycleState.INSTALLED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.INSTALLED: [IntegrationLifecycleState.AUTHENTICATED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.AUTHENTICATED: [IntegrationLifecycleState.VERIFIED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.VERIFIED: [IntegrationLifecycleState.ENABLED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.ENABLED: [IntegrationLifecycleState.HEALTHY, IntegrationLifecycleState.DEGRADED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.HEALTHY: [IntegrationLifecycleState.ACTIVE, IntegrationLifecycleState.DEGRADED, IntegrationLifecycleState.QUARANTINED],
        IntegrationLifecycleState.ACTIVE: [IntegrationLifecycleState.DEGRADED, IntegrationLifecycleState.QUARANTINED, IntegrationLifecycleState.REVOKED],
        IntegrationLifecycleState.DEGRADED: [IntegrationLifecycleState.HEALTHY, IntegrationLifecycleState.QUARANTINED, IntegrationLifecycleState.REVOKED],
        IntegrationLifecycleState.QUARANTINED: [IntegrationLifecycleState.VALIDATED, IntegrationLifecycleState.REVOKED],
        IntegrationLifecycleState.REVOKED: []  # Terminal state
    }

    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry
        self._states: Dict[str, IntegrationLifecycleState] = {}

    def get_state(self, integration_id: str) -> IntegrationLifecycleState:
        return self._states.get(integration_id, IntegrationLifecycleState.DISCOVERED)

    def transition_state(self, integration_id: str, new_state: IntegrationLifecycleState) -> bool:
        current_state = self.get_state(integration_id)
        if new_state not in self.ALLOWED_TRANSITIONS.get(current_state, []):
            raise ValueError(f"Invalid state transition from {current_state} to {new_state}")

        self._states[integration_id] = new_state
        if new_state == IntegrationLifecycleState.REVOKED:
            self.provider_registry.revoke_provider(integration_id)

        return True

    def revoke_integration(self, integration_id: str, reason: str) -> bool:
        self._states[integration_id] = IntegrationLifecycleState.REVOKED
        self.provider_registry.revoke_provider(integration_id)
        return True
