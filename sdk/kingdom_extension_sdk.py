"""
Kingdom Extension SDK.
Typed client SDK allowing external developers to register tools, declare capabilities, subscribe to events, and interface with Kingdom.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

@dataclass
class ExtensionConfig:
    extension_id: str
    name: str
    version: str
    required_capabilities: List[str]
    required_permissions: List[str]

class KingdomExtensionSDK:
    def __init__(self, config: ExtensionConfig, kingdom_api_url: str = "http://localhost:8000"):
        self.config = config
        self.kingdom_api_url = kingdom_api_url
        self._tools: Dict[str, Callable] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}

    def register_tool_handler(self, tool_id: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self._tools[tool_id] = handler

    def subscribe_event(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def handle_tool_call(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._tools.get(tool_id)
        if not handler:
            raise KeyError(f"No handler registered for tool: {tool_id}")
        return handler(params)

    def dispatch_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            handler(payload)
