"""Browser readiness cannot advertise safe public background control."""
from backend.runtime.agent_api import browser_readiness


def test_browser_readiness_is_disabled_and_not_certified_by_default(monkeypatch):
    monkeypatch.delenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', raising=False)
    monkeypatch.delenv('KINGDOM_BROWSER_ALLOWED_HOSTS', raising=False)
    result = browser_readiness()
    assert result['ready_for_disposable_testing'] is False
    assert result['public_release_certified'] is False
    assert result['owner_destination_count'] == 0
    assert 'Experimental browser mode is disabled' in result['blockers']


def test_browser_readiness_requires_valid_owner_host_policy(monkeypatch):
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'localhost,example.org')
    result = browser_readiness()
    assert result['owner_destination_count'] == 0
    assert 'No valid owner-configured browser domains' in result['blockers']
    assert result['public_release_certified'] is False


def test_browser_readiness_reports_configured_domain_count_without_leaking_hosts(monkeypatch):
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'example.org,example.net')
    result = browser_readiness()
    assert result['owner_destination_count'] == 2
    assert result['public_release_certified'] is False
    assert 'example.org' not in str(result)
