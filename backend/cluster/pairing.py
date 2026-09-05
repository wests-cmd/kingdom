import time
import secrets
import json
import base64
from typing import Dict, Any, Optional
from backend.cluster.identity import KingdomIdentity, compute_fingerprint
from backend.cluster.node_registry import node_registry, NodeState
from backend.events.event_bus import event_bus

class PairingManager:
    def __init__(self, kingdom_identity: Optional[KingdomIdentity] = None):
        self.kingdom_identity = kingdom_identity or KingdomIdentity.get_or_create()
        self._invitations: Dict[str, Dict[str, Any]] = {}

    def create_invitation(self, ttl_seconds: int = 600) -> Dict[str, Any]:
        code = secrets.token_hex(4).upper()
        formatted_code = f"{code[:4]}-{code[4:]}"
        now = time.time()
        expires_at = now + ttl_seconds

        invitation = {
            "code": formatted_code,
            "kingdom_id": self.kingdom_identity.node_id,
            "kingdom_display_name": self.kingdom_identity.display_name,
            "kingdom_fingerprint": self.kingdom_identity.fingerprint,
            "kingdom_public_key_hex": self.kingdom_identity.public_bytes.hex(),
            "created_at": now,
            "expires_at": expires_at,
            "used": False
        }
        self._invitations[formatted_code] = invitation

        # QR Code payload JSON
        qr_data = json.dumps({
            "kingdom_id": invitation["kingdom_id"],
            "kingdom_display_name": invitation["kingdom_display_name"],
            "fingerprint": invitation["kingdom_fingerprint"],
            "public_key_hex": invitation["kingdom_public_key_hex"],
            "code": formatted_code,
            "expires_at": expires_at
        })
        invitation["qr_payload"] = base64.b64encode(qr_data.encode("utf-8")).decode("utf-8")

        event_bus.publish("cluster.pairing_invitation_created", {
            "code": formatted_code,
            "expires_at": expires_at
        }, source="pairing_manager")
        return invitation

    def verify_invitation(self, code: str) -> Optional[Dict[str, Any]]:
        inv = self._invitations.get(code)
        if not inv:
            return None
        if inv["used"]:
            return None
        if time.time() > inv["expires_at"]:
            return None
        return inv

    def process_pairing_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        request_payload = {
            "code": "7X4P-92KM",
            "expected_kingdom_id": "KG-MASTER-01",
            "knight_public_identity": {
                "node_id": "KN-82A1F9",
                "display_name": "Knight Gaming PC",
                "public_key_hex": "...",
                "fingerprint": "..."
            },
            "requested_capabilities": ["compute", "gpu"],
            "signature": "..." # Optional request signature signed by Knight private key
        }
        """
        code = request_payload.get("code")
        inv = self.verify_invitation(code)
        if not inv:
            return {"success": False, "error": "Invalid, expired, or already used pairing code."}

        # Cross-Kingdom Protection: Ensure Knight expects THIS Kingdom
        expected_k_id = request_payload.get("expected_kingdom_id")
        if expected_k_id and expected_k_id != self.kingdom_identity.node_id:
            return {"success": False, "error": f"Cross-Kingdom mismatch: Request target {expected_k_id} does not match {self.kingdom_identity.node_id}"}

        knight_pub = request_payload.get("knight_public_identity")
        if not knight_pub or not knight_pub.get("node_id") or not knight_pub.get("public_key_hex"):
            return {"success": False, "error": "Missing Knight public identity information."}

        node_id = knight_pub["node_id"]
        pub_hex = knight_pub["public_key_hex"]
        computed_fp = compute_fingerprint(bytes.fromhex(pub_hex))

        # Identity Substitution Protection: Check if node_id exists with different fingerprint
        existing_node = node_registry.get_node(node_id)
        if existing_node and existing_node.get("fingerprint"):
            if existing_node["fingerprint"] != computed_fp:
                # Security Alert: Identity key substitution detected!
                node_registry.update_node_state(node_id, NodeState.QUARANTINED, reason="Identity substitution attempt detected")
                event_bus.publish("security.identity_substitution_detected", {
                    "node_id": node_id,
                    "previous_fingerprint": existing_node["fingerprint"],
                    "presented_fingerprint": computed_fp
                }, source="pairing_manager")
                return {
                    "success": False,
                    "error": "SECURITY WARNING: Knight identity fingerprint has changed! Potential impersonation attack.",
                    "security_alert": True
                }

        # Verify signature if provided
        sig_hex = request_payload.get("signature")
        if sig_hex:
            msg = f"{code}:{node_id}:{self.kingdom_identity.node_id}".encode("utf-8")
            if not KingdomIdentity.verify_signature(pub_hex, msg, bytes.fromhex(sig_hex)):
                return {"success": False, "error": "Invalid request signature verification."}

        # Mark invitation as used
        inv["used"] = True

        # Register or update node state to PENDING_APPROVAL
        node_registry.register_discovered_node({
            "id": node_id,
            "role": "knight",
            "node_state": NodeState.PENDING_APPROVAL.value,
            "capabilities": request_payload.get("requested_capabilities", []),
            "granted_capabilities": [], # Default deny until approved
            "public_identity": knight_pub,
            "fingerprint": computed_fp,
            "kingdom_id": self.kingdom_identity.node_id,
            "is_local": request_payload.get("is_local", False),
            "connection_metadata": request_payload.get("connection_metadata", {})
        })

        event_bus.publish("cluster.pairing_requested", {
            "node_id": node_id,
            "kingdom_id": self.kingdom_identity.node_id,
            "fingerprint": computed_fp
        }, source="pairing_manager")

        return {
            "success": True,
            "node_id": node_id,
            "status": NodeState.PENDING_APPROVAL.value,
            "kingdom_identity": self.kingdom_identity.get_public_identity(),
            "message": "Pairing request received. Waiting for Kingdom human approval."
        }

pairing_manager = PairingManager()
