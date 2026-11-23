"""Experimental headless browser computer-use adapter.

Runs in a new Chromium browser context, never in the user's interactive desktop.
It is NOT an OS sandbox; it is disabled unless explicitly enabled for testing.
Kingdom's existing task policy and owner approvals remain authoritative.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

MAX_ACTIONS = 8
MAX_HOSTS = 4
MAX_TEXT = 6000
MIN_AVAILABLE_MEMORY_BYTES = 768 * 1024 * 1024
_ALLOWED_KEYS = {'Enter', 'Tab', 'Escape', 'Backspace', 'ArrowDown', 'ArrowUp'}
_HOST = re.compile(r'^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$', re.ASCII)


def validate_host(value):
    """Exact public DNS names only; raw IPs, local names and wildcards are denied."""
    if not isinstance(value, str) or len(value) > 253 or value != value.strip():
        raise ValueError('Browser host must be an exact public DNS name')
    host = value.lower()
    if not _HOST.fullmatch(host) or '..' in host or '.' not in host:
        raise ValueError('Browser host must be an exact public DNS name')
    if host.endswith(('.local', '.internal', '.localhost', '.test', '.invalid',
                      '.example', '.nip.io', '.sslip.io', '.localtest.me', '.lvh.me')):
        raise ValueError('Browser host is not a public DNS destination')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Browser IP literals are forbidden')
    if any(not label or label.startswith('-') or label.endswith('-') or len(label) > 63
           for label in host.split('.')):
        raise ValueError('Malformed browser hostname')
    return host


def allowed_url(value, hosts):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(x) < 33 for x in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and parsed.hostname in hosts and
                (parsed.port is None or parsed.port == 443) and
                not parsed.username and not parsed.password and
                not parsed.fragment and parsed.hostname is not None)
    except (ValueError, TypeError):
        return False


def validate_plan(params):
    """Validate the full request before any browser/network operation."""
    if not isinstance(params, dict) or set(params) - {
        'start_url', 'allowed_hosts', 'actions', '_receipt_id'
    }:
        raise ValueError('Unknown browser plan fields')
    hosts = params.get('allowed_hosts')
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= MAX_HOSTS:
        raise ValueError('Choose one to four approved public domains')
    normalized = frozenset(validate_host(host) for host in hosts)
    if len(normalized) != len(hosts):
        raise ValueError('Duplicate approved domain')
    if not allowed_url(params.get('start_url'), normalized):
        raise ValueError('Starting URL must use HTTPS on an approved domain')
    actions = params.get('actions', [])
    if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
        raise ValueError('At most eight browser actions are supported')
    checked = []
    for action in actions:
        if not isinstance(action, dict) or action.get('action') not in {
            'navigate', 'click', 'fill', 'press'
        }:
            raise ValueError('Unknown browser action')
        operation = action['action']
        fields = {
            'navigate': {'action', 'url'}, 'click': {'action', 'selector'},
            'fill': {'action', 'selector', 'text'},
            'press': {'action', 'selector', 'key'},
        }[operation]
        if set(action) != fields:
            raise ValueError('Browser action has missing or unexpected fields')
        if operation == 'navigate':
            if not allowed_url(action['url'], normalized):
                raise ValueError('Navigation must remain on approved HTTPS domains')
        else:
            selector = action.get('selector')
            if not isinstance(selector, str) or not 1 <= len(selector) <= 300 or '\x00' in selector:
                raise ValueError('Browser action requires a bounded selector')
            if operation == 'fill':
                text = action['text']
                if not isinstance(text, str) or len(text) > 1000 or any(ord(ch) < 32 for ch in text):
                    raise ValueError('Only short printable form input is allowed')
            if operation == 'press' and action['key'] not in _ALLOWED_KEYS:
                raise ValueError('Unsupported browser key')
        checked.append(action.copy())
    return normalized, checked


def ensure_browser_memory_budget():
    """Do not start Chromium when it would starve the owner's desktop.

    This is admission only; OS process isolation/limits remain mandatory for
    certified unattended use.
    """
    try:
        import psutil
        available = psutil.virtual_memory().available
    except Exception as error:
        raise RuntimeError('Cannot verify safe browser memory headroom') from error
    if not isinstance(available, int) or available < MIN_AVAILABLE_MEMORY_BYTES:
        raise RuntimeError('Insufficient free RAM for a private browser; use an approved larger worker')
    return available


def run_isolated_browser(params, *, guard=None):
    """Operate a disposable headless browser; never call OS mouse/keyboard APIs.

    Feature flag plus owner-configured domains are separate from model arguments.
    Browser interception is NOT network/VM containment: host egress controls and
    DNS-rebinding tests are required before releasing unattended internet control.
    """
    hosts, actions = validate_plan(params)
    receipt_id = params.get('_receipt_id')
    if not isinstance(receipt_id, str) or not 1 <= len(receipt_id) <= 128:
        raise ValueError('The governed task identity is required before any browser action')
    if os.environ.get('KINGDOM_EXPERIMENTAL_ISOLATED_BROWSER') != '1':
        raise PermissionError('Isolated browser preview is disabled until explicitly enabled for testing')
    if not callable(guard):
        raise PermissionError('Browser tool requires a trusted execution guard from the governed task')
    guard()
    try:
        approved = frozenset(validate_host(item) for item in
                             os.environ.get('KINGDOM_BROWSER_ALLOWED_HOSTS', '').split(',') if item)
    except ValueError as error:
        raise PermissionError('Invalid server browser destination policy') from error
    if not approved or not hosts.issubset(approved):
        raise PermissionError('Browser destination is not approved by the owner configuration')
    ensure_browser_memory_budget()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError('Optional isolated browser runtime is not installed') from error

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                accept_downloads=False, service_workers='block', permissions=[],
                viewport={'width': 1120, 'height': 760},
                java_script_enabled=True, ignore_https_errors=False)
            try:
                def restrict(route):
                    # Check every outbound request, including dynamic requests
                    # a page schedules after the initial navigation. A stopped
                    # job must not initiate another network fetch.
                    guard()
                    request = route.request
                    # A webpage may create requests the model never asked for.
                    # The preview is read-only at the HTTP layer: block writes.
                    if not allowed_url(request.url, hosts) or request.method not in {'GET', 'HEAD'}:
                        route.abort('blockedbyclient')
                        return
                    # Explicitly reject all redirects rather than following a
                    # second destination that lacks an independent site grant.
                    response = route.fetch(max_redirects=0, timeout=5000)
                    if 300 <= response.status < 400:
                        route.abort('blockedbyclient')
                        return
                    route.fulfill(response=response)

                context.route('**/*', restrict)
                # BrowserContext.route does NOT cover WebSockets. Do not
                # launch a page if WebSocket routing is unavailable. This
                # interception does NOT replace OS-level network filtering.
                if not callable(getattr(context, 'route_web_socket', None)):
                    raise RuntimeError('Playwright WebSocket interception is required')
                context.route_web_socket('**/*', lambda websocket: websocket.close())
                page = context.new_page()
                context.on('page', lambda popup: popup.close() if popup != page else None)
                page.set_default_timeout(5000)
                page.set_default_navigation_timeout(10000)
                guard()
                page.goto(params['start_url'], wait_until='domcontentloaded')
                if not allowed_url(page.url, hosts):
                    raise PermissionError('Browser redirected outside approved domains')
                for step in actions:
                    # An owner stop/revocation during the sequence fences each new effect.
                    guard()
                    operation = step['action']
                    if operation == 'navigate':
                        page.goto(step['url'], wait_until='domcontentloaded')
                    elif operation == 'click':
                        page.locator(step['selector']).click(timeout=5000)
                    elif operation == 'fill':
                        page.locator(step['selector']).fill(step['text'], timeout=5000)
                    elif operation == 'press':
                        page.locator(step['selector']).press(step['key'], timeout=5000)
                    if not allowed_url(page.url, hosts):
                        raise PermissionError('Browser left approved HTTPS domains')
                guard()
                from backend.runtime.computer_tools import workspace_path
                directory = workspace_path('browser-captures')
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                if os.name == 'posix':
                    directory.chmod(0o700)
                capture = workspace_path('browser-captures/' + hashlib.sha256(receipt_id.encode()).hexdigest() + '.png')
                screenshot = page.screenshot(full_page=False, timeout=5000)
                temporary_path = None
                try:
                    with tempfile.NamedTemporaryFile(dir=directory, suffix='.tmp', delete=False) as temporary:
                        temporary_path = Path(temporary.name)
                        if os.name == 'posix':
                            os.chmod(temporary.name, 0o600)
                        temporary.write(screenshot)
                        temporary.flush()
                        os.fsync(temporary.fileno())
                    temporary_path.replace(capture)
                finally:
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)
                return {
                    'url': page.url, 'title': page.title()[:300],
                    'text': page.locator('body').inner_text(timeout=5000)[:MAX_TEXT],
                    'actions_completed': len(actions), 'headless': True,
                    'uses_user_desktop': False, 'approved_hosts': sorted(hosts),
                    'capture': str(capture),
                    'capture_sha256': hashlib.sha256(screenshot).hexdigest(),
                    'verification_limit': 'Rendered browser evidence only; no independent goal-completion assertion',
                }
            finally:
                context.close()
        finally:
            browser.close()
