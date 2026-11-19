"""Node authentication, identity management, and capability binding."""

from __future__ import annotations

import secrets
from threading import RLock
from typing import Any

from backend.security.capabilities import DEFAULT_KNIGHT_CAPABILITIES


class NodeSecurityManager:
    """Manages identity, credentials, and granted capabilities for Knights/Nodes."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, str] = {}  # token -> node_id
        self._lock = RLock()
        # Pre-register default built-in knights and system actor with automatic tokens
        self._init_default_knights()

    def _init_default_knights(self) -> None:
        from backend.security.capabilities import ALL_CAPABILITIES

        default_identities = ["planner", "coder", "researcher", "memory", "security", "system"]
        for actor in default_identities:
            token = secrets.token_urlsafe(48)
            self.register_node(
                node_id=actor,
                name=f"Identity ({actor.title()})",
                capabilities=set(DEFAULT_KNIGHT_CAPABILITIES),
                token=token,
            )
        self.register_node(
            node_id="admin",
            name="Identity (Admin)",
            capabilities=set(ALL_CAPABILITIES),
            token=secrets.token_urlsafe(48),
        )
        from backend.security.http_auth import owner_auth
        self.register_node("owner", name="Authenticated human owner", capabilities=set(ALL_CAPABILITIES), token=owner_auth.token)

    def register_node(
        self,
        node_id: str,
        name: str | None = None,
        capabilities: set[str] | list[str] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Register or rotate a node credential without leaving the old credential active."""
        if not isinstance(node_id, str) or not node_id or len(node_id) > 128:
            raise ValueError("A bounded node ID is required")
        if token is not None and (not isinstance(token, str) or not token or len(token) > 1024 or not token.isascii()):
            raise ValueError("A valid nonempty node token is required")

        caps = set(capabilities) if capabilities is not None else set(DEFAULT_KNIGHT_CAPABILITIES)
        with self._lock:
            node_token = token if token is not None else f"node-tok-{secrets.token_hex(16)}"
            previous_owner = self._tokens.get(node_token)
            if previous_owner is not None and previous_owner != node_id:
                raise ValueError("A credential may not be assigned to a different node")
            old_record = self._nodes.get(node_id)
            old_token = old_record.get("token") if old_record else None
            if old_token is not None and old_token != node_token:
                self._tokens.pop(old_token, None)
            record = {
                "node_id": node_id,
                "name": name or node_id,
                "token": node_token,
                "capabilities": list(caps),
                "verified": True,
                "active": True,
            }
            self._nodes[node_id] = record
            self._tokens[node_token] = node_id
            return record

    def authenticate_token(self, token: str) -> str | None:
        """Authenticate active nodes without token lookup short-circuiting.

        Walk all registered credentials, as proposed by the timing-hardening
        branch. Reject malformed tokens before comparing them.
        """
        if not isinstance(token, str) or not token or len(token) > 1024 or not token.isascii():
            return None
        matched_id = None
        with self._lock:
            for registered_token, node_id in self._tokens.items():
                if secrets.compare_digest(registered_token, token):
                    node = self._nodes.get(node_id)
                    if node and node.get("active"):
                        matched_id = node_id
        return matched_id

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
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node["active"] = False
                token = node.get("token")
                if token:
                    self._tokens.pop(token, None)

    def list_nodes(self) -> list[dict[str, Any]]:
        # Return list without raw tokens for security
        result = []
        for n in self._nodes.values():
            copy_node = dict(n)
            copy_node.pop("token", None)
            result.append(copy_node)
        return result
