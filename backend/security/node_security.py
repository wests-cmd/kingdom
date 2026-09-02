"""Node authentication, identity management, and capability binding."""

from __future__ import annotations

import secrets
from typing import Any

from backend.security.capabilities import DEFAULT_KNIGHT_CAPABILITIES


class NodeSecurityManager:
    """Manages identity, credentials, and granted capabilities for Knights/Nodes."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, str] = {}  # token -> node_id
        # Pre-register default built-in knights and system actor with automatic tokens
        self._init_default_knights()

    def _init_default_knights(self) -> None:
        default_identities = ["planner", "coder", "researcher", "memory", "security", "system"]
        for actor in default_identities:
            token = f"kingdom-internal-{actor}-token"
            self.register_node(
                node_id=actor,
                name=f"Identity ({actor.title()})",
                capabilities=set(DEFAULT_KNIGHT_CAPABILITIES),
                token=token,
            )

    def register_node(
        self,
        node_id: str,
        name: str | None = None,
        capabilities: set[str] | list[str] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        node_token = token or f"node-tok-{secrets.token_hex(16)}"
        caps = set(capabilities) if capabilities else set(DEFAULT_KNIGHT_CAPABILITIES)

        node_record = {
            "node_id": node_id,
            "name": name or node_id,
            "token": node_token,
            "capabilities": list(caps),
            "verified": True,
            "active": True,
        }

        self._nodes[node_id] = node_record
        self._tokens[node_token] = node_id
        return node_record

    def authenticate_token(self, token: str) -> str | None:
        """Returns node_id if token is valid and active, otherwise None."""
        node_id = self._tokens.get(token)
        if node_id:
            node = self._nodes.get(node_id)
            if node and node.get("active"):
                return node_id
        return None

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    def get_node_capabilities(self, node_id: str) -> set[str]:
        node = self._nodes.get(node_id)
        if not node or not node.get("active"):
            return set()
        return set(node.get("capabilities", []))

    def update_node_capabilities(self, node_id: str, capabilities: list[str] | set[str]) -> dict[str, Any]:
        node = self._nodes.get(node_id)
        if not node:
            raise KeyError(f"Node '{node_id}' not found")
        node["capabilities"] = list(set(capabilities))
        return node

    def revoke_node(self, node_id: str) -> None:
        node = self._nodes.get(node_id)
        if node:
            node["active"] = False
            token = node.get("token")
            if token and token in self._tokens:
                del self._tokens[token]

    def list_nodes(self) -> list[dict[str, Any]]:
        # Return list without raw tokens for security
        result = []
        for n in self._nodes.values():
            copy_node = dict(n)
            copy_node.pop("token", None)
            result.append(copy_node)
        return result
