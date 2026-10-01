import time
import secrets
import json
from threading import RLock
from functools import wraps
from typing import Dict, Any, Optional
from enum import Enum
from backend.cluster.identity import KingdomIdentity, compute_fingerprint
from backend.cluster.node_registry import node_registry, NodeState
from backend.events.event_bus import event_bus

class MobileDeviceState(str, Enum):
    UNPAIRED = "unpaired"
    PENDING = "pending"
    PAIRED = "paired"
    TRUSTED = "trusted"
    RESTRICTED = "restricted"
    REVOKED = "revoked"
    OFFLINE = "offline"

def locked(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


class MobilePairingManager:
    def __init__(self, kingdom_identity: Optional[KingdomIdentity] = None):
        self.kingdom_identity = kingdom_identity or KingdomIdentity.get_or_create()
        self._pairing_challenges: Dict[str, Dict[str, Any]] = {}
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    @locked
    def create_pairing_challenge(self, ttl_seconds: int = 300) -> Dict[str, Any]:
        challenge_code = secrets.token_hex(8).upper()
        formatted_code = f"{challenge_code[:8]}-{challenge_code[8:]}"
        now = time.time()
        expires_at = now + ttl_seconds
        self._pairing_challenges = {code: item for code, item in self._pairing_challenges.items()
                                    if not item["used"] and item["expires_at"] > now}
        self._active_sessions = {token: item for token, item in self._active_sessions.items()
                                 if item["expires_at"] > now}
        if len(self._pairing_challenges) >= 100:
            oldest = min(self._pairing_challenges, key=lambda code: self._pairing_challenges[code]["created_at"])
            del self._pairing_challenges[oldest]

        challenge = {
            "code": formatted_code,
            "kingdom_id": self.kingdom_identity.node_id,
            "kingdom_display_name": self.kingdom_identity.display_name,
            "kingdom_fingerprint": self.kingdom_identity.fingerprint,
            "created_at": now,
            "expires_at": expires_at,
            "used": False
        }
        self._pairing_challenges[formatted_code] = challenge

        event_bus.publish("mobile.pairing_challenge_created", {
            "expires_at": expires_at
        }, source="mobile_pairing")
        return challenge

    @locked
    def process_mobile_pairing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        payload = {
            "code": "7X4P-92KM",
            "device_id": "phone-iphone15-user01",
            "device_name": "John's iPhone",
            "device_public_key_hex": "...",
            "signature": "..."
        }
        """
        code = str(payload.get("code", "")).strip().upper()
        ch = self._pairing_challenges.get(code)
        if not ch or ch["used"] or time.time() > ch["expires_at"]:
            return {"success": False, "error": "Invalid, expired, or already used mobile pairing code."}

        device_id = payload.get("device_id")
        device_name = payload.get("device_name", device_id)
        pub_hex = payload.get("device_public_key_hex")
        sig_hex = payload.get("signature")

        if not device_id or not pub_hex or not sig_hex:
            return {"success": False, "error": "Missing device identity or signature."}
        if node_registry.get_node(device_id):
            return {"success": False, "error": "Device identity already exists. Use a new identity."}

        # Verify signature
        msg = f"{code}:{device_id}:{self.kingdom_identity.node_id}".encode("utf-8")
        try:
            signature = bytes.fromhex(sig_hex)
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid device signature encoding."}
        if not KingdomIdentity.verify_signature(pub_hex, msg, signature):
            return {"success": False, "error": "Mobile proof-of-possession signature verification failed."}

        # Mark challenge used
        ch["used"] = True

        # Generate scoped mobile session token
        session_token = f"mbl_sess_{secrets.token_hex(16)}"
        fingerprint = compute_fingerprint(bytes.fromhex(pub_hex))

        # Register mobile device node in registry under PENDING_APPROVAL / RESTRICTED state
        node_registry.register_discovered_node({
            "id": device_id,
            "role": "mobile_gateway",
            "node_state": NodeState.PENDING_APPROVAL.value,
            "capabilities": [],  # Browser companion currently supports only its own pairing status.
            "granted_capabilities": [],  # No capabilities before explicit owner approval.
            "public_identity": {
                "node_id": device_id,
                "node_type": "mobile",
                "display_name": device_name,
                "public_key_hex": pub_hex,
                "fingerprint": fingerprint
            },
            "fingerprint": fingerprint,
            "kingdom_id": self.kingdom_identity.node_id
        })

        session = {
            "device_id": device_id,
            "device_name": device_name,
            "session_token": session_token,
            "state": MobileDeviceState.PENDING.value,
            "created_at": time.time(),
            "expires_at": time.time() + 86400
        }
        self._active_sessions[session_token] = session

        event_bus.publish("mobile.device_paired", {
            "device_id": device_id,
            "device_name": device_name,
            "fingerprint": fingerprint
        }, source="mobile_pairing")

        return {
            "success": True,
            "device_id": device_id,
            "session_token": session_token,
            "device_state": MobileDeviceState.PENDING.value,
            "kingdom_identity": self.kingdom_identity.get_public_identity(),
            "message": "Mobile device successfully paired. Awaiting Commander human approval."
        }

    @locked
    def session_status(self, token: str) -> Dict[str, Any]:
        session = self._active_sessions.get(token)
        if not session or session["expires_at"] <= time.time():
            return {"success": False, "error": "Device session expired. Pair again."}
        node = node_registry.get_node(session["device_id"])
        if not node or node.node_state in {NodeState.REVOKED.value, NodeState.REJECTED.value}:
            return {"success": False, "error": "Device access was revoked or rejected."}
        return {"success": True, "device_id": session["device_id"],
                "device_name": session["device_name"], "device_state": node.node_state,
                "kingdom_display_name": self.kingdom_identity.display_name,
                "capabilities": node.granted_capabilities}

    @locked
    def approve_mobile_device(self, device_id: str) -> bool:
        node = node_registry.get_node(device_id)
        if not node or node.role != "mobile_gateway" or node.node_state != NodeState.PENDING_APPROVAL.value:
            return False
        node_registry.update_node_state(device_id, NodeState.APPROVED)
        event_bus.publish("mobile.device_approved", {"device_id": device_id}, source="mobile_pairing")
        return True

    @locked
    def revoke_mobile_device(self, device_id: str, reason: str = "User revocation") -> bool:
        node = node_registry.get_node(device_id)
        if not node:
            return False
        node_registry.update_node_state(device_id, NodeState.REVOKED, reason=reason)
        # Invalidate active sessions for device
        for token, sess in list(self._active_sessions.items()):
            if sess["device_id"] == device_id:
                sess["state"] = MobileDeviceState.REVOKED.value
                del self._active_sessions[token]
        event_bus.publish("mobile.device_revoked", {"device_id": device_id, "reason": reason}, source="mobile_pairing")
        return True

mobile_pairing_manager = MobilePairingManager()
