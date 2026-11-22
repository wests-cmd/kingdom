"""Fail-closed checks for the optional non-interfering browser computer-use tool."""
from contextlib import contextmanager
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from backend.runtime.isolated_browser import allowed_url, run_isolated_browser, validate_plan


@pytest.mark.parametrize('url', [
    'http://example.org', 'https://127.0.0.1/', 'https://localhost/',
    'file:///etc/passwd', 'https://example.org:444/',
    'https://example.org@attacker.net/', 'https://example.org.evil.net/',
    'https://example.org/#fragment', 'https://example.org/\n',
])
def test_rejects_unapproved_network_and_local_urls(url):
    assert not allowed_url(url, {'example.org'})


@pytest.mark.parametrize('host', [
    'localhost', '127.0.0.1', '*.example.org', 'example.org:443',
    'localhost.local', 'intranet.internal', 'x.test', 'EXAMPLE.ORG.',
    'example.org/other', 'example..org', '127.0.0.1.nip.io',
])
def test_invalid_hosts_do_not_pass_validation(host):
    with pytest.raises(ValueError):
        validate_plan({'start_url': 'https://example.org', 'allowed_hosts': [host]})


def test_whitelisted_https_navigation_and_bounded_actions():
    hosts, actions = validate_plan({
        'start_url': 'https://example.org/', 'allowed_hosts': ['Example.Org'],
        'actions': [
            {'action': 'fill', 'selector': '#query', 'text': 'test'},
            {'action': 'press', 'selector': '#query', 'key': 'Enter'},
        ],
    })
    assert hosts == {'example.org'}
    assert len(actions) == 2


@pytest.mark.parametrize('bad_action', [
    {'action': 'evaluate', 'javascript': 'fetch("http://127.0.0.1")'},
    {'action': 'navigate', 'url': 'http://example.org'},
    {'action': 'navigate', 'url': 'https://private.example.org'},
    {'action': 'fill', 'selector': '#a', 'text': 'hello\nworld'},
    {'action': 'click', 'selector': '#a', 'script': 'alert(1)'},
    {'action': 'press', 'selector': '#a', 'key': 'Meta+R'},
])
def test_rejects_unapproved_or_ambiguous_actions_before_browser_launch(bad_action):
    with pytest.raises(ValueError):
        run_isolated_browser({
            'start_url': 'https://example.org',
            'allowed_hosts': ['example.org'], 'actions': [bad_action],
            '_receipt_id': 'test',
        })


def test_experimental_browser_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', raising=False)
    with pytest.raises(PermissionError, match='disabled'):
        run_isolated_browser({'start_url': 'https://example.org',
                              'allowed_hosts': ['example.org'],
                              'actions': [], '_receipt_id': 'test'})


def test_browser_can_only_use_server_owner_approved_hosts(monkeypatch):
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'example.org')
    with pytest.raises(PermissionError, match='not approved'):
        run_isolated_browser({'start_url': 'https://different.org',
                              'allowed_hosts': ['different.org'],
                              'actions': [], '_receipt_id': 'test'})


def test_headless_browser_uses_private_context_and_not_user_input(monkeypatch, tmp_path):
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'example.org')
    monkeypatch.chdir(tmp_path)
    events = []

    class Locator:
        def __init__(self, selector):
            self.selector = selector
        def click(self, **kw):
            events.append(('click', self.selector))
        def fill(self, value, **kw):
            events.append(('fill', self.selector, value))
        def press(self, key, **kw):
            events.append(('press', self.selector, key))
        def inner_text(self, **kw):
            return 'mock visible page'

    class Page:
        url = 'https://example.org/'
        def set_default_timeout(self, value):
            events.append(('timeout', value))
        def set_default_navigation_timeout(self, value):
            events.append(('navigation_timeout', value))
        def goto(self, url, **kw):
            self.url = url
            events.append(('navigate', url))
        def locator(self, selector):
            return Locator(selector)
        def screenshot(self, **kw):
            return b'MOCKPNG'
        def title(self):
            return 'Mock page'

    class Context:
        def __init__(self):
            self.page = Page()
        def route(self, pattern, fn):
            events.append(('route', pattern))
            blocked = SimpleNamespace(
                request=SimpleNamespace(url='http://127.0.0.1/', method='GET'),
                abort=lambda reason: events.append(('blocked', reason)),
            )
            fn(blocked)
            allowed = SimpleNamespace(
                request=SimpleNamespace(url='https://example.org/', method='GET'),
                fetch=lambda **kw: events.append(('fetch', kw)) or SimpleNamespace(status=200),
                fulfill=lambda **kw: events.append(('fulfill', kw)),
            )
            fn(allowed)
            unsafe_write = SimpleNamespace(
                request=SimpleNamespace(url='https://example.org/', method='POST'),
                abort=lambda reason: events.append(('write_blocked', reason)),
            )
            fn(unsafe_write)
            redirect = SimpleNamespace(
                request=SimpleNamespace(url='https://example.org/', method='GET'),
                fetch=lambda **kw: SimpleNamespace(status=302),
                abort=lambda reason: events.append(('redirect_blocked', reason)),
                fulfill=lambda **kw: events.append(('redirect_fulfilled',)),
            )
            fn(redirect)
        def route_web_socket(self, pattern, fn):
            events.append(('websocket_route', pattern))
            fn(SimpleNamespace(close=lambda: events.append(('websocket_blocked',))))
        def new_page(self):
            return self.page
        def on(self, *args):
            pass
        def close(self):
            events.append(('context_close',))

    class Browser:
        def new_context(self, **kw):
            assert kw['service_workers'] == 'block'
            assert kw['accept_downloads'] is False
            assert kw['permissions'] == []
            events.append(('context',))
            return Context()
        def close(self):
            events.append(('browser_close',))

    class Chromium:
        def launch(self, **kw):
            assert kw == {'headless': True}
            events.append(('headless_launch',))
            return Browser()

    @contextmanager
    def sync_playwright():
        yield SimpleNamespace(chromium=Chromium())

    monkeypatch.setitem(sys.modules, 'playwright', SimpleNamespace(sync_api=None))
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', SimpleNamespace(sync_playwright=sync_playwright))
    result = run_isolated_browser({
        'start_url': 'https://example.org/',
        'allowed_hosts': ['example.org'],
        'actions': [{'action': 'click', 'selector': 'button'}],
        '_receipt_id': 'fake-task',
    }, guard=lambda: events.append(('task_guard',)))
    assert events.count(('task_guard',)) >= 3
    assert result['headless'] and result['uses_user_desktop'] is False
    assert result['capture_sha256'] and Path(result['capture']).parts[:2] == ('data', 'browser-captures')
    assert ('blocked', 'blockedbyclient') in events
    assert ('write_blocked', 'blockedbyclient') in events
    assert ('redirect_blocked', 'blockedbyclient') in events
    assert ('redirect_fulfilled',) not in events
    assert ('websocket_blocked',) in events
    assert ('fetch', {'max_redirects': 0, 'timeout': 5000}) in events
    assert ('click', 'button') in events
    assert ('context_close',) in events and ('browser_close',) in events


def test_governed_receipt_identity_is_required_before_effects(monkeypatch):
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'example.org')
    with pytest.raises(ValueError, match='governed task identity'):
        run_isolated_browser({'start_url': 'https://example.org',
                              'allowed_hosts': ['example.org'], 'actions': []})



def test_browser_denies_preview_without_trusted_task_guard(monkeypatch):
    monkeypatch.setenv('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER', '1')
    monkeypatch.setenv('KINGDOM_BROWSER_ALLOWED_HOSTS', 'example.org')
    with pytest.raises(PermissionError, match='trusted execution guard'):
        run_isolated_browser({
            'start_url': 'https://example.org/',
            'allowed_hosts': ['example.org'], 'actions': [],
            '_receipt_id': 'untrusted-task',
        })
