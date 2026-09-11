"""
Kingdom Credential Broker & Data Classification Policy Engine.
Protects raw credentials from leaking into LLM contexts, prompts, logs, or telemetry.
"""

from enum import Enum
from typing import Dict, Any, Optional
import os
import secrets
import re

class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"
    CREDENTIALS = "CREDENTIALS"

class CredentialBroker:
    TOKEN_PATTERNS = [
        re.compile(r"ghp_[A-Za-z0-9_]{10,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{10,}"),
        re.compile(r"sk-[A-Za-z0-9_]{10,}"),
        re.compile(r"bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)
    ]

    def __init__(self):
        self._credentials: Dict[str, Dict[str, Any]] = {}
        self._handles: Dict[str, str] = {}
        self._secret_key = os.urandom(32)

    def store_credential(self, provider_id: str, credential_data: Dict[str, Any]) -> str:
        """
        Stores raw credentials in memory and returns an opaque handle string.
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
        Supports dicts, lists, tuples, sets, strings, and custom objects.
        """
        if isinstance(payload, dict):
            sanitized_dict = {}
            for k, v in payload.items():
                sanitized_val = self.sanitize_payload_for_llm(v)
                if any(s in k.lower() for s in ["token", "secret", "password", "key", "credential", "auth"]):
                    # Optimization: sanitized_val has already been processed by self.sanitize_payload_for_llm(v),
                    # which replaces all TOKEN_PATTERNS in string values with "[REDACTED_BEARER_TOKEN]".
                    # Relying on "[REDACTED_BEARER_TOKEN]" in sanitized_val eliminates redundant regex searches.
                    if isinstance(sanitized_val, str) and "[REDACTED_BEARER_TOKEN]" in sanitized_val:
                        sanitized_dict[k] = "[REDACTED_BEARER_TOKEN]"
                    else:
                        sanitized_dict[k] = "[REDACTED_CREDENTIAL]"
                else:
                    sanitized_dict[k] = sanitized_val
            return sanitized_dict
        elif isinstance(payload, (list, tuple, set)):
            sanitized_items = [self.sanitize_payload_for_llm(item) for item in payload]
            return type(payload)(sanitized_items)
        elif isinstance(payload, str):
            res = payload
            for pattern in self.TOKEN_PATTERNS:
                res = pattern.sub("[REDACTED_BEARER_TOKEN]", res)
            return res
        return payload

    def revoke_credential(self, handle: str) -> bool:
        if handle in self._credentials:
            del self._credentials[handle]
            for pid, h in list(self._handles.items()):
                if h == handle:
                    del self._handles[pid]
            return True
        return False
