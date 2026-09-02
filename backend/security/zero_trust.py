from backend.security.permissions import permission_manager

class ZeroTrust:

    def __init__(self, manager=None):
        self.permission_manager = manager or permission_manager

    def validate(self, actor, required_capability=None):
        if not actor or not isinstance(actor, dict):
            return {
                "actor": actor,
                "trusted": False,
                "authorized": False,
                "reason": "Invalid or missing actor context"
            }

        actor_id = actor.get("id") or actor.get("name") or "unknown"
        is_verified = bool(actor.get("verified", False))

        if not is_verified and actor.get("role") != "admin":
            return {
                "actor": actor_id,
                "trusted": False,
                "authorized": False,
                "reason": "Actor identity is unverified"
            }

        if required_capability:
            has_cap = self.permission_manager.check_capability(actor, required_capability)
            if not has_cap:
                return {
                    "actor": actor_id,
                    "trusted": True,
                    "authorized": False,
                    "capability": required_capability,
                    "reason": f"Capability '{required_capability}' not granted to actor"
                }

        return {
            "actor": actor_id,
            "trusted": True,
            "authorized": True,
            "capability": required_capability,
            "reason": "Authorization granted"
        }
