import httpx
import pytest
from sdk.kingdom_sdk import KingdomSDK


def test_sdk_uses_explicit_owner_auth_and_csrf_header(monkeypatch):
    actual_client = httpx.Client
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"running": False})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: actual_client(**kwargs, transport=httpx.MockTransport(handler)))
    sdk = KingdomSDK(owner_token="controlled-test-credential-not-a-real-owner")
    try:
        assert sdk.get_status() == {"running": False}
        assert requests[0].headers["Authorization"] == "Bearer controlled-test-credential-not-a-real-owner"
        assert requests[0].headers["X-Kingdom-Request"] == "1"
    finally:
        sdk.close()


@pytest.mark.parametrize("address", ["http://example.com", "https://user:password@example.com", "https://example.com/?token=secret", "ftp://example.com"])
def test_sdk_refuses_unsafe_owner_credential_destinations(address):
    with pytest.raises(ValueError):
        KingdomSDK(address, owner_token="controlled-test-credential-not-a-real-owner")
