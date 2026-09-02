import secrets
from backend.security.permissions import permission_manager

class TrustEngine:

    def __init__(self):
        self.nodes = {}

    def score(self, node):
        if not node or not isinstance(node, dict):
            return 0.0

        trust = 0.3

        if node.get("verified"):
            trust += 0.3

        if node.get("role") in ["commander", "admin"]:
            trust += 0.2

        if node.get("auth_token"):
            trust += 0.2

        return min(trust, 1.0)

    def register_node(self, node_id, role="knight", capabilities=None, auth_token=None):
        if not node_id:
            raise ValueError("node_id is required for node registration")

        token = auth_token or secrets.token_hex(16)
        caps = capabilities or permission_manager.get_role_capabilities(role)

        node_profile = {
            "id": node_id,
            "role": role,
            "capabilities": caps,
            "auth_token": token,
            "verified": True
        }

        self.nodes[node_id] = node_profile
        return node_profile

    def authenticate_node(self, node_id, token):
        node = self.nodes.get(node_id)
        if not node:
            return False
        if not token:
            return False
        return secrets.compare_digest(node.get("auth_token", ""), token)

    def get_node(self, node_id):
        return self.nodes.get(node_id)

# Global instance
trust_engine = TrustEngine()
