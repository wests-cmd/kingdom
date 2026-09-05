import time
import json
import secrets
from typing import Dict, Any, Optional
from backend.cluster.identity import BaseNodeIdentity, KingdomIdentity, KnightIdentity
from backend.cluster.node_registry import node_registry, NodeState
from backend.events.event_bus import event_bus

PROTOCOL_VERSION = "kingdom.cluster.v1"
MAX_TIME_SKEW_SECONDS = 300.0  # 5 minutes

class RPCMessage:
    def __init__(self, sender_id: str, target_id: str, msg_type: str, payload: Dict[str, Any], msg_id: Optional[str] = None, timestamp: Optional[float] = None):
        self.protocol_version = PROTOCOL_VERSION
        self.msg_id = msg_id or secrets.token_hex(8)
        self.sender_id = sender_id
        self.target_id = target_id
        self.msg_type = msg_type
        self.payload = payload
        self.timestamp = timestamp or time.time()

    def get_canonical_bytes(self) -> bytes:
        data = {
            "protocol_version": self.protocol_version,
            "msg_id": self.msg_id,
            "sender_id": self.sender_id,
            "target_id": self.target_id,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "timestamp": self.timestamp
        }
        return json.dumps(data, sort_keys=True).encode("utf-8")

    def to_dict(self, signature: Optional[str] = None) -> Dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "msg_id": self.msg_id,
            "sender_id": self.sender_id,
            "target_id": self.target_id,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "signature": signature
        }


class RPCSecureTransport:
    def __init__(self, node_identity: BaseNodeIdentity):
        self.identity = node_identity
        self._processed_msg_ids: set = set()

    def create_signed_message(self, target_id: str, msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        msg = RPCMessage(sender_id=self.identity.node_id, target_id=target_id, msg_type=msg_type, payload=payload)
        canonical = msg.get_canonical_bytes()
        sig = self.identity.sign_message(canonical)
        return msg.to_dict(signature=sig.hex())

    def verify_and_unwrap_message(self, message_dict: Dict[str, Any], expected_target_id: Optional[str] = None) -> Dict[str, Any]:
        # Protocol version validation
        if message_dict.get("protocol_version") != PROTOCOL_VERSION:
            return {"valid": False, "error": f"Protocol mismatch. Expected {PROTOCOL_VERSION}, got {message_dict.get('protocol_version')}"}

        msg_id = message_dict.get("msg_id")
        if not msg_id or msg_id in self._processed_msg_ids:
            return {"valid": False, "error": "Replay attack detected or duplicate message ID."}

        timestamp = message_dict.get("timestamp", 0)
        now = time.time()
        if abs(now - timestamp) > MAX_TIME_SKEW_SECONDS:
            return {"valid": False, "error": f"Message timestamp expired or clock skew too large. Timestamp: {timestamp}, Now: {now}"}

        target_id = message_dict.get("target_id")
        check_target = expected_target_id or self.identity.node_id
        if target_id != check_target:
            return {"valid": False, "error": f"Message addressed to wrong target node {target_id}. Expected {check_target}."}

        sender_id = message_dict.get("sender_id")
        sender_node = node_registry.get_node(sender_id)
        if not sender_node and sender_id != check_target:
            # Allow sender if sender_id is Kingdom identity itself during verification
            pass

        # Check sender node state if node exists in registry
        if sender_node:
            state = sender_node.get("node_state")
            if state in [NodeState.REVOKED.value, NodeState.REJECTED.value, NodeState.QUARANTINED.value]:
                return {"valid": False, "error": f"Sender node {sender_id} is in revoked or restricted state: {state}."}

        pub_identity = sender_node.get("public_identity") if sender_node else None
        pub_key_hex = pub_identity.get("public_key_hex") if pub_identity else None

        sig_hex = message_dict.get("signature")
        if not sig_hex:
            return {"valid": False, "error": "Missing signature in RPC message."}

        # Construct canonical RPCMessage
        msg = RPCMessage(
            sender_id=sender_id,
            target_id=target_id,
            msg_type=message_dict["msg_type"],
            payload=message_dict["payload"],
            msg_id=msg_id,
            timestamp=timestamp
        )
        canonical = msg.get_canonical_bytes()

        if pub_key_hex:
            valid_sig = BaseNodeIdentity.verify_signature(pub_key_hex, canonical, bytes.fromhex(sig_hex))
            if not valid_sig:
                event_bus.publish("security.rpc_invalid_signature", {"sender_id": sender_id, "msg_id": msg_id}, source="rpc_transport")
                return {"valid": False, "error": "Invalid cryptographic signature."}

        # Cache msg_id to prevent replay attacks
        self._processed_msg_ids.add(msg_id)
        if len(self._processed_msg_ids) > 10000:
            self._processed_msg_ids.clear()

        return {
            "valid": True,
            "sender_id": sender_id,
            "target_id": target_id,
            "msg_type": message_dict["msg_type"],
            "payload": message_dict["payload"],
            "msg_id": msg_id
        }
