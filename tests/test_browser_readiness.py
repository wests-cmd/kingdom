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



def test_browser_readiness_fails_closed_for_playwright_without_websocket_support(monkeypatch, tmp_path):
    import importlib.util
    import sys
    from contextlib import contextmanager
    from types import ModuleType, SimpleNamespace
    binary = tmp_path / 'test-chromium'
    binary.write_bytes(b'not-a-browser')
    @contextmanager
    def fake_playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(executable_path=str(binary)))
    package = ModuleType('playwright')
    package.__path__ = []
    api = ModuleType('playwright.sync_api')
    api.sync_playwright = fake_playwright
    api.BrowserContext = type('OldPlaywrightContext', (), {})
    monkeypatch.setitem(sys.modules, 'playwright', package)
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', api)
    find_spec = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, 'find_spec',
                        lambda name: object() if name == 'playwright' else find_spec(name))
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'example.org')
    result = browser_readiness()
    assert result['adapter_installed'] is True
    assert result['headless_browser_binary_present'] is True
    assert result['websocket_interception_available'] is False
    assert result['ready_for_disposable_testing'] is False
    assert any('WebSocket interception unavailable' in reason for reason in result['blockers'])
