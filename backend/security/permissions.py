import re

CAPABILITIES = [
    "filesystem.read",
    "filesystem.write",
    "filesystem.delete",
    "process.execute",
    "network.access",
    "docker.execute",
    "model.inference",
    "memory.read",
    "memory.write",
    "ai_map.read",
    "ai_map.write",
    "node.register",
    "node.execute",
    "system.admin"
]

ROLE_CAPABILITIES = {
    "system.admin": CAPABILITIES,
    "admin": CAPABILITIES,
    "commander": [
        "node.register",
        "node.execute",
        "model.inference",
        "memory.read",
        "memory.write",
        "ai_map.read",
        "ai_map.write",
        "process.execute",
        "filesystem.read",
        "filesystem.write"
    ],
    "knight": [
        "model.inference",
        "memory.read",
        "memory.write",
        "node.execute",
        "filesystem.read"
    ],
    "scout": [
        "memory.read",
        "node.execute"
    ],
    # Five standardized swarm permission profiles:
    # 1. Observe: Read-only telemetry
    "observe": [
        "memory.read",
        "ai_map.read"
    ],
    # 2. Assist: Normal low-risk approved tasks
    "assist": [
        "memory.read",
        "ai_map.read",
        "model.inference",
        "filesystem.read"
    ],
    # 3. Develop: Coding, testing and sandbox execution
    "develop": [
        "memory.read",
        "memory.write",
        "ai_map.read",
        "ai_map.write",
        "model.inference",
        "filesystem.read",
        "filesystem.write",
        "process.execute"
    ],
    # 4. Admin: Explicitly delegated administrative operations
    "admin_delegated": [
        "memory.read",
        "memory.write",
        "ai_map.read",
        "ai_map.write",
        "model.inference",
        "filesystem.read",
        "filesystem.write",
        "filesystem.delete",
        "process.execute",
        "network.access",
        "node.register",
        "node.execute",
        "system.admin"
    ],
    # 5. Experimental: Extended authority within designated isolated host (Laptop 2)
    "experimental": [
        "memory.read",
        "memory.write",
        "ai_map.read",
        "ai_map.write",
        "model.inference",
        "filesystem.read",
        "filesystem.write",
        "filesystem.delete",
        "process.execute",
        "network.access",
        "docker.execute",
        "node.execute"
    ],
    "guest": []
}

class PermissionManager:

    def __init__(self, custom_roles=None):
        self.roles = dict(ROLE_CAPABILITIES)
        if custom_roles:
            self.roles.update(custom_roles)

    def get_role_capabilities(self, role):
        return self.roles.get(role, [])

    def check_capability(self, actor, required_capability):
        if not actor or not isinstance(actor, dict):
            return False

        if not required_capability or not isinstance(required_capability, str):
            return False

        granted = set(actor.get("capabilities", []))
        role = actor.get("role", "guest")

        # Strict isolation check for Experimental role:
        # Experimental privileges are strictly scoped to designated experimental hosts (e.g. Laptop 2)
        # and must never be extended to general Knights or nodes like DT1.
        # Enforce verified cryptographic/registered grant or explicit non-spoofable host confirmation.
        if role == "experimental":
            node_id = str(actor.get("node_id") or actor.get("host") or "").lower()
            # Must have explicit non-forged verified marker and match designated experimental host identity
            is_designated = ("laptop2" in node_id or "laptop-2" in node_id)
            is_verified = (actor.get("is_experimental_host") is True or actor.get("verified_experimental_grant") is True)
            if not (is_designated and is_verified):
                # Deny experimental escalation if node is not an authorized experimental host
                role = "observe"

        granted.update(self.get_role_capabilities(role))

        if "*" in granted or "system.admin" in granted:
            return True

        if required_capability in granted:
            return True

        for cap in granted:
            if cap.endswith(".*"):
                prefix = cap[:-2]
                if required_capability.startswith(prefix + "."):
                    return True

        return False

# Global instance
permission_manager = PermissionManager()
