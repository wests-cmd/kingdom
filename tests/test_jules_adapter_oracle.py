"""Trusted controller assertion tests; no Docker execution/signing claim."""
import base64
import importlib.util
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import urllib.request
import urllib.error
from contextlib import contextmanager


def load():
    spec = importlib.util.spec_from_file_location('adapter_oracle', Path(__file__).parents[1]/'scripts/jules-adapter-oracle.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_discovery_api_cannot_pass_with_fake_junit_or_success_text():
    module = load()
    def missing(method, path, headers, body):
        return {'status': 404, 'truncated': False,
                'body': base64.b64encode(b'99 passed <testsuite tests="99" failures="0"/>').decode()}
    results = module.AdapterReadinessSuite(missing, 'disposable-owner-token').run()
    assert results and all(not case['passed'] for case in results)
    assert len(results) == len(module.CASES)


@contextmanager
def candidate_api(*, hardcoded=False, configured_ready=False, forged_auth=False):
    """External HTTP boundary simulator, not candidate or production evidence."""
    profiles = {}
    token = 'disposable-owner-token'
    jules = {'enabled': False, 'has_credentials': False, 'revision': 1}
    def unavailable():
        return {'connected': False, 'available_to_planner': False, 'protocol_verified': False,
                'granted_execution_authority': False, 'authenticated': False, 'acp_compliant': False,
                'unavailable_reasons': ['No independent connection evidence']}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self): self.exchange()
        def do_PUT(self): self.exchange()
        def exchange(self):
            if self.headers.get('Authorization') != 'Bearer ' + token:
                status, value = (200, {'tools': [], 'models': []}) if forged_auth else (403, {'detail': 'denied'})
            elif self.path == '/chatgpt-plan': status, value = 200, {'state': 'sign_in_required', 'enabled': False}
            elif self.path == '/runtime/policy': status, value = 200, {'level': 5}
            elif self.path == '/integrations/jules/settings':
                if self.command == 'PUT':
                    json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                    jules.update(enabled=True, has_credentials=True, revision=2)
                status, value = 200, dict(jules)
            elif self.path.startswith('/workspace/model-profiles/') and self.command == 'PUT':
                ident = self.path.rsplit('/', 1)[1]
                profiles[ident] = {**json.loads(self.rfile.read(int(self.headers['Content-Length']))), 'id': ident}
                status, value = 200, profiles[ident]
            elif self.path == '/workspace/model-profiles': status, value = 200, {'profiles': list(profiles.values())}
            elif self.path == '/integrations/adapters':
                models = [] if hardcoded else [{'id': p['id'], 'name': p['model'], 'source': 'configured_profile',
                    'available': False, 'unavailable_reasons': ['Endpoint not verified']} for p in profiles.values()]
                if configured_ready:
                    for p in models:
                        p.update(available=True, unavailable_reasons=[])
                status, value = 200, {'tools': [{'id': ident, **unavailable()} for ident in ('codex', 'jules', 'ollama')], 'models': models}
            elif self.path == '/integrations/adapters/jules/connectivity':
                status, value = 200, {'id': 'jules', **unavailable()}
                if configured_ready and jules['enabled']:
                    value.update(connected=True, authenticated=True, available_to_planner=True)
            else: status, value = 404, {'detail': 'missing'}
            data = json.dumps(value).encode()
            self.send_response(status); self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    def transport(method, path, headers, body):
        request = urllib.request.Request('http://127.0.0.1:' + str(server.server_port) + path,
            method=method, headers=headers, data=None if body is None else body.encode())
        try: response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as e: response = e
        with response:
            data = response.read(65537)
            return {'status': response.status, 'body': base64.b64encode(data[:65536]).decode(), 'truncated': len(data) > 65536}
    try: yield transport, token
    finally: server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_real_http_controller_roundtrips_custom_profiles_without_inference():
    with candidate_api() as (transport, token):
        results = load().AdapterReadinessSuite(transport, token).run()
    assert all(r['passed'] for r in results), results


def test_hardcoded_inventory_and_configured_ready_claims_fail_external_assertions():
    for options in ({'hardcoded': True}, {'configured_ready': True}, {'forged_auth': True}):
        with candidate_api(**options) as (transport, token):
            results = load().AdapterReadinessSuite(transport, token).run()
        assert any(not r['passed'] for r in results), options
        by_name = {r['name']: r for r in results}
        if options.get('hardcoded'): assert not by_name['custom_profile_roundtrip']['passed']
        if options.get('configured_ready'): assert not by_name['configured_is_not_verified']['passed']
        if options.get('forged_auth'): assert not by_name['forged_owner_rejected']['passed']


def test_synthetic_jules_secret_and_allowlist_are_not_provider_authentication():
    with candidate_api(configured_ready=True) as (transport, token):
        results = load().AdapterReadinessSuite(transport, token).run()
    result = next(row for row in results if row['name'] == 'configured_jules_not_verified')
    assert result['passed'] is False


def test_adapter_contract_must_be_hash_bound_by_protected_supervisor():
    spec = importlib.util.spec_from_file_location('supervisor', Path(__file__).parents[1]/'scripts/jules-external-review.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert 'jules-adapter-oracle.py' in module.contract_files('adapter-readiness-v1')
    assert module.contract_digest('adapter-readiness-v1') != module.contract_digest('api-negative-fences')


def test_changing_installed_assertions_changes_only_its_own_contract_hash(tmp_path):
    import shutil
    source = Path(__file__).parents[1]/'scripts'
    for name in ('jules-external-review.py', 'jules-source-preparation.py', 'jules-external-oracle.py',
                 'archive-verified-source.py', 'jules-adapter-oracle.py'):
        shutil.copyfile(source/name, tmp_path/name)
    spec = importlib.util.spec_from_file_location('copied_supervisor', tmp_path/'jules-external-review.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    before = module.contract_digest('adapter-readiness-v1')
    negative = module.contract_digest('api-negative-fences')
    with (tmp_path/'jules-adapter-oracle.py').open('a') as handle: handle.write('\n# changed installed assertion contract\n')
    assert module.contract_digest('adapter-readiness-v1') != before
    assert module.contract_digest('api-negative-fences') == negative


def test_oversized_or_credential_disclosing_responses_are_never_success_signals():
    for body, truncated in ((b'x'*65537, False), (b'disposable-owner-token', False), (b'{}', True)):
        def hostile(*args):
            return {'status': 200, 'body': base64.b64encode(body).decode(), 'truncated': truncated}
        result = load().AdapterReadinessSuite(hostile, 'disposable-owner-token').run()
        assert all(not row['passed'] for row in result)
        assert all('disposable-owner-token' not in row['detail'] for row in result)
