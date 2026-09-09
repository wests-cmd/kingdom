"""
Kingdom Extension Runtime, Scoped Event API & Isolated Data API.
Enforces extension event authorization, namespace data isolation, and rate-limiting throttling.
"""

from typing import Dict, Any, List, Optional, Callable
import time

class ExtensionRuntime:
    def __init__(self):
        self._namespaces: Dict[str, Dict[str, Any]] = {}
        self._authorized_subscriptions: Dict[str, List[str]] = {}
        self._rate_limits: Dict[str, Dict[str, float]] = {}  # ext_id -> {last_call, call_count}

    def initialize_extension_namespace(self, extension_id: str, allowed_events: List[str]) -> None:
        self._namespaces[extension_id] = {}
        self._authorized_subscriptions[extension_id] = allowed_events
        self._rate_limits[extension_id] = {"last_call": 0.0, "call_count": 0}

    def write_isolated_data(self, extension_id: str, key: str, value: Any) -> None:
        if extension_id not in self._namespaces:
            raise KeyError(f"Unregistered extension namespace: {extension_id}")
        self._namespaces[extension_id][key] = value

    def read_isolated_data(self, extension_id: str, key: str, caller_extension_id: str) -> Any:
        if caller_extension_id != extension_id:
            raise PermissionError("Cross-extension data access is strictly prohibited")
        return self._namespaces.get(extension_id, {}).get(key)

    def subscribe_event(self, extension_id: str, event_type: str) -> bool:
        allowed = self._authorized_subscriptions.get(extension_id, [])
        if event_type not in allowed and "*" not in allowed:
            raise PermissionError(f"Extension {extension_id} is not authorized to subscribe to event: {event_type}")
        return True

    def check_rate_limit(self, extension_id: str, max_calls_per_sec: int = 10) -> bool:
        now = time.time()
        record = self._rate_limits.get(extension_id, {"last_call": 0.0, "call_count": 0})
        if now - record["last_call"] > 1.0:
            record["last_call"] = now
            record["call_count"] = 1
            return True
        elif record["call_count"] < max_calls_per_sec:
            record["call_count"] += 1
            return True
        else:
            return False
