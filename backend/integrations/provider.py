"""
Kingdom Provider Abstraction & Provider Registry.
Defines the ProviderBase interface and central ProviderRegistry tracking health, rate limits, and authentication state.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import time

class ProviderHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    REVOKED = "REVOKED"

@dataclass
class ProviderMetrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_call_timestamp: float = 0.0
    last_error: Optional[str] = None
    rate_limit_remaining: int = 1000
    rate_limit_reset: float = 0.0

class ProviderBase(ABC):
    def __init__(self, provider_id: str, name: str, version: str):
        self.provider_id = provider_id
        self.name = name
        self.version = version
        self.metrics = ProviderMetrics()
        self.health_status = ProviderHealthStatus.UNAUTHENTICATED

    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def check_health(self) -> ProviderHealthStatus:
        pass

    @abstractmethod
    def execute_operation(self, operation: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        pass

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, ProviderBase] = {}

    def register_provider(self, provider: ProviderBase) -> None:
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> Optional[ProviderBase]:
        return self._providers.get(provider_id)

    def list_providers(self) -> List[Dict[str, Any]]:
        return [
            {
                "provider_id": p.provider_id,
                "name": p.name,
                "version": p.version,
                "health_status": p.health_status.value,
                "metrics": {
                    "total_calls": p.metrics.total_calls,
                    "successful_calls": p.metrics.successful_calls,
                    "failed_calls": p.metrics.failed_calls,
                    "last_error": p.metrics.last_error
                }
            }
            for p in self._providers.values()
        ]

    def revoke_provider(self, provider_id: str) -> bool:
        p = self._providers.get(provider_id)
        if p:
            p.health_status = ProviderHealthStatus.REVOKED
            return True
        return False
