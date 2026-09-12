"""
Tests for CredentialBroker and DataClassification sanitization.
"""

import pytest
from backend.security.credential_broker import CredentialBroker, DataClassification

def test_credential_broker_storage_and_isolation():
    broker = CredentialBroker()
    handle = broker.store_credential("org.kingdom.github", {"token": "ghp_SECRET_TOKEN_123456"})

    assert handle.startswith("cred_handle_")
    assert broker.get_handle("org.kingdom.github") == handle

    # Execute isolated operation
    def call_api(cred):
        return f"Authenticated with {cred['token'][:4]}..."

    result = broker.execute_with_credential(handle, call_api)
    assert result == "Authenticated with ghp_..."

def test_llm_payload_sanitization():
    broker = CredentialBroker()
    raw_payload = {
        "status": "success",
        "access_token": "ghp_SECRET_TOKEN_123456",
        "api_secret": "my_super_secret_key",
        "user": {
            "name": "Alice",
            "api_key": "sk-1234567890"
        },
        "items": ["bearer 123456", "public_data"]
    }

    sanitized = broker.sanitize_payload_for_llm(raw_payload)

    assert sanitized["access_token"] == "[REDACTED_BEARER_TOKEN]"
    assert sanitized["api_secret"] == "[REDACTED_CREDENTIAL]"
    assert sanitized["user"]["api_key"] == "[REDACTED_BEARER_TOKEN]"
    assert sanitized["user"]["name"] == "Alice"
    assert sanitized["items"][0] == "[REDACTED_BEARER_TOKEN]"
    assert sanitized["items"][1] == "public_data"

def test_credential_revocation():
    broker = CredentialBroker()
    handle = broker.store_credential("org.kingdom.github", {"token": "ghp_SECRET"})
    assert broker.revoke_credential(handle) is True

    with pytest.raises(KeyError):
        broker.execute_with_credential(handle, lambda c: c)
