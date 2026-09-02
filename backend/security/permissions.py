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
