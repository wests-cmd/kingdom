import os
import hashlib
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

IDENTITY_DIR = os.path.join("data", "identities")

def ensure_identity_dir():
    os.makedirs(IDENTITY_DIR, exist_ok=True)

def compute_fingerprint(public_bytes: bytes) -> str:
    digest = hashlib.sha256(public_bytes).hexdigest().upper()
    return ":".join(digest[i:i+2] for i in range(0, 32, 2))

class BaseNodeIdentity:
    def __init__(self, node_id: str, node_type: str, private_key: Optional[ed25519.Ed25519PrivateKey] = None, display_name: str = ""):
        self.node_id = node_id
        self.node_type = node_type  # "commander" or "knight"
        self.display_name = display_name or node_id
        if private_key is None:
            self.private_key = ed25519.Ed25519PrivateKey.generate()
        else:
            self.private_key = private_key
        self.public_key = self.private_key.public_key()
        self.public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self.fingerprint = compute_fingerprint(self.public_bytes)

    def sign_message(self, message: bytes) -> bytes:
        return self.private_key.sign(message)

    def get_public_identity(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "display_name": self.display_name,
            "public_key_hex": self.public_bytes.hex(),
            "fingerprint": self.fingerprint,
        }

    @staticmethod
    def verify_signature(public_key_hex: str, message: bytes, signature: bytes) -> bool:
        try:
            public_bytes = bytes.fromhex(public_key_hex)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            pub_key.verify(signature, message)
            return True
        except Exception:
            return False

    def save_to_file(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        priv_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        data = {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "display_name": self.display_name,
            "private_key_pem": priv_pem.decode("utf-8"),
            "fingerprint": self.fingerprint
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str):
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = json.load(f)
        priv_pem = data["private_key_pem"].encode("utf-8")
        private_key = serialization.load_pem_private_key(priv_pem, password=None)
        return cls._create_from_loaded(
            node_id=data["node_id"],
            node_type=data["node_type"],
            private_key=private_key,
            display_name=data.get("display_name", "")
        )

    @classmethod
    def _create_from_loaded(cls, node_id: str, node_type: str, private_key: ed25519.Ed25519PrivateKey, display_name: str):
        if node_type == "commander":
            return KingdomIdentity(kingdom_id=node_id, display_name=display_name, private_key=private_key)
        else:
            return KnightIdentity(knight_id=node_id, display_name=display_name, private_key=private_key)


class KingdomIdentity(BaseNodeIdentity):
    def __init__(self, kingdom_id: str = "KG-MASTER-01", display_name: str = "Kingdom Commander", private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        super().__init__(node_id=kingdom_id, node_type="commander", private_key=private_key, display_name=display_name)

    @classmethod
    def get_or_create(cls, filepath: Optional[str] = None) -> "KingdomIdentity":
        ensure_identity_dir()
        path = filepath or os.path.join(IDENTITY_DIR, "kingdom_identity.json")
        identity = cls.load_from_file(path)
        if identity is None:
            identity = cls()
            identity.save_to_file(path)
        return identity


class KnightIdentity(BaseNodeIdentity):
    def __init__(self, knight_id: str, display_name: str = "", private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        super().__init__(node_id=knight_id, node_type="knight", private_key=private_key, display_name=display_name)

    @classmethod
    def get_or_create(cls, knight_id: str, display_name: str = "", filepath: Optional[str] = None) -> "KnightIdentity":
        ensure_identity_dir()
        path = filepath or os.path.join(IDENTITY_DIR, f"knight_{knight_id}.json")
        identity = cls.load_from_file(path)
        if identity is None:
            identity = cls(knight_id=knight_id, display_name=display_name)
            identity.save_to_file(path)
        return identity
