import time
from typing import Any, Dict, List, Optional, Callable
from backend.extensions.models import ExtensionTrustState
from backend.extensions.registry import ExtensionRegistry


class ExtensionEventBus:

    def __init__(self, registry: ExtensionRegistry, max_events_per_sec: int = 100):
        self.registry = registry
        self.max_events_per_sec = max_events_per_sec
        self.handlers: Dict[str, List[Callable]] = {}
        self.event_timestamps: List[float] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    def publish(self, event_type: str, payload: Dict[str, Any], event_permission: Optional[str] = None) -> int:
        now = time.time()
        # Rate limiting check
        self.event_timestamps = [t for t in self.event_timestamps if now - t < 1.0]
        if len(self.event_timestamps) >= self.max_events_per_sec:
            raise RuntimeError(f"ExtensionEventBus rate limit exceeded ({len(self.event_timestamps)} events/sec)")

        self.event_timestamps.append(now)

        delivered = 0
        enabled_extensions = self.registry.list_extensions(state=ExtensionTrustState.ENABLED)

        for ext in enabled_extensions:
            manifest = ext.manifest
            if event_type in manifest.subscribed_events:
                # Check event permission if specified
                if event_permission and event_permission not in manifest.permissions:
                    continue

                for handler in self.handlers.get(event_type, []):
                    try:
                        handler(payload)
                        delivered += 1
                    except Exception as e:
                        ext.error_count += 1
                        ext.last_error = f"Event error ({event_type}): {str(e)}"

        return delivered
