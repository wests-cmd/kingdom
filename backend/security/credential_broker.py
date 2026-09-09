"""
Kingdom Credential Broker & Data Classification Policy Engine.
Protects raw credentials from leaking into LLM contexts, prompts, logs, or telemetry.
"""

from enum import Enum
from typing import Dict, Any, Optional
import os
import secrets
import hmac
import hashlib

class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"
    CREDENTIALS = "CREDENTIALS"

class CredentialBroker:
    def __init__(self):
        self._credentials: Dict[str, Dict[str, Any]] = {}
        self._handles: Dict[str, str] = {}
        self._secret_key = os.urandom(32)

    def store_credential(self, provider_id: str, credential_data: Dict[str, Any]) -> str:
        """
        Stores raw credentials in memory and returns a opaque handle string.
        Raw credentials are never returned to external callers.
        """
        handle = f"cred_handle_{secrets.token_hex(16)}"
        self._credentials[handle] = credential_data
        self._handles[provider_id] = handle
        return handle

    def get_handle(self, provider_id: str) -> Optional[str]:
        return self._handles.get(provider_id)

    def execute_with_credential(self, handle: str, executor_func) -> Any:
        """
        Executes a callable with access to the raw credential in isolated local scope.
        The caller must not leak the raw credential from the executor function.
        """
        cred = self._credentials.get(handle)
        if not cred:
            raise KeyError("Invalid or expired credential handle")
        return executor_func(cred)

    def sanitize_payload_for_llm(self, payload: Any) -> Any:
        """
        Recursively scrubs any credential values or token patterns from payloads before LLM ingestion.
        """
        if isinstance(payload, dict):
            return {
                k: "[REDACTED_CREDENTIAL]" if "token" in k.lower() or "secret" in k.lower() or "password" in k.lower() or "key" in k.lower()
                else self.sanitize_payload_for_llm(v)
                for k, v in payload.items()
            }
        elif isinstance(payload, list):
            return [self.sanitize_payload_for_llm(item) for item in payload]
        elif isinstance(payload, str):
            if payload.startswith("ghp_") or payload.startswith("sk-") or payload.startswith("bearer "):
                return "[REDACTED_BEARER_TOKEN]"
        return payload

    def revoke_credential(self, handle: str) -> bool:
        if handle in self._credentials:
            del self._credentials[handle]
            for pid, h in list(self._handles.items()):
                if h == handle:
                    del self._handles[pid]
            return True
        return False
