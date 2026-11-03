"""Fixed host assertions for adapter readiness, never candidate test results.

The candidate serves only bounded HTTP data. Tests, counts and signing remain
outside its container. This contract does not exercise installs or model calls.
"""
import base64
import importlib.util
import json
import subprocess
from pathlib import Path
import time
import uuid


CONTRACT_ID = 'adapter-readiness-v2'
ALLOWED_PATHS = [
    'backend/integrations/acp_adapters.py', 'backend/integrations/adapter_api.py',
    'backend/main.py', 'docs/ADAPTER_CAPABILITY_DISCOVERY.md',
    'frontend/src/components/AdapterDiscovery.jsx', 'frontend/src/pages/Integrations.jsx',
    'frontend/src/pages/Settings.jsx', 'tests/test_acp_adapters.py',
    'frontend/tests/adapterDiscovery.test.js',
]
CASES = ('unauthenticated_discovery', 'forged_owner_rejected',
         'fresh_readiness_not_invented', 'unconfigured_jules_not_connected',
         'custom_profile_roundtrip', 'configured_is_not_verified', 'configured_jules_not_verified')
EXTRA_CASES = ('inventory_reads_do_not_initialize_state', 'unrelated_chatgpt_catalog_unavailable')
DISCLAIMER = ('Fixed adapter-readiness API assertions only; no ACP negotiation, '
              'app installation, model inference, general patch or release acceptance. '
              'Saved-ready SQL fixture tests model identity isolation, not actual inference.')


def base_module():
    spec = importlib.util.spec_from_file_location('protected_adapter_base', Path(__file__).with_name('jules-external-oracle.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = base_module()  # Trusted installed sibling, never candidate source.


class AdapterReadinessSuite:
    """Fixed external assertion seam; transport returns untrusted HTTP envelopes."""
    def __init__(self, transport, token):
        self.transport = transport
        self.token = token

    def response(self, method, path, body=None, *, auth=True, forged=False):
        headers = {'Content-Type': 'application/json', 'X-Kingdom-Request': '1'}
        if auth:
            headers['Authorization'] = 'Bearer ' + ('invalid-external-review-token' if forged else self.token)
        value = self.transport(method, path, headers, None if body is None else json.dumps(body))
        if (not isinstance(value, dict) or value.get('truncated') is not False
                or type(value.get('status')) is not int or not 100 <= value['status'] <= 599):
            raise ValueError('Invalid bounded HTTP response envelope')
        raw = base64.b64decode(value.get('body', ''), validate=True)
        if len(raw) > 65536 or self.token.encode() in raw or b'invalid-disposable-external-review-key' in raw:
            raise ValueError('Oversized response or disposable credential disclosed')
        return value['status'], raw

    def request(self, method, path, body=None):
        status, raw = self.response(method, path, body)
        if status not in (200, 201):
            raise AssertionError('Required real API endpoint unavailable')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise AssertionError('Required JSON object absent')
        return value

    def discovery(self):
        value = self.request('GET', '/integrations/adapters')
        if not isinstance(value.get('tools'), list) or not isinstance(value.get('models'), list):
            raise AssertionError('Real tool/model inventory required')
        if (not value['tools'] or len(value['tools']) > 100 or len(value['models']) > 1000
                or any(not isinstance(row, dict) for row in [*value['tools'], *value['models']])):
            raise AssertionError('Bounded inventory objects required')
        return value

    @staticmethod
    def unavailable(row):
        reasons = row.get('unavailable_reasons')
        if not isinstance(reasons, list) or not reasons or any(not isinstance(r, str) or not r or len(r) > 1000 for r in reasons):
            raise AssertionError('Unavailable facts need explicit bounded reasons')

    def unauthenticated(self):
        status, _ = self.response('GET', '/integrations/adapters', auth=False)
        assert status in (401, 403), 'Missing route or validation is not authentication enforcement'

    def forged(self):
        status, _ = self.response('GET', '/integrations/adapters', forged=True)
        assert status in (401, 403), 'Forged token must not become owner'

    def fresh_readiness(self):
        chat = self.request('GET', '/chatgpt-plan')
        assert chat.get('state') == 'sign_in_required' and chat.get('enabled') is False
        inventory = self.discovery()
        tools = {row.get('id'): row for row in inventory['tools']}
        assert {'codex', 'jules', 'ollama'} <= tools.keys(), 'Expected supported adapter inspection absent'
        for ident in ('codex', 'jules', 'ollama'):
            row = tools[ident]
            for flag in ('connected', 'authenticated', 'available_to_planner', 'protocol_verified', 'acp_compliant', 'granted_execution_authority'):
                assert row.get(flag) is False, 'Fresh unconfigured state cannot assert readiness/authority'
            assert row.get('status') not in ('ready', 'connected', 'authenticated')
            self.unavailable(row)
        for model in inventory['models']:
            assert model.get('available') is False, 'Fresh catalog metadata is not installed/authenticated availability'
            self.unavailable(model)

    def jules_unconfigured(self):
        settings = self.request('GET', '/integrations/jules/settings')
        assert settings.get('enabled') is False and settings.get('has_credentials') is False
        row = self.request('GET', '/integrations/adapters/jules/connectivity')
        assert row.get('id') == 'jules'
        for flag in ('connected', 'authenticated', 'available_to_planner', 'protocol_verified', 'acp_compliant', 'granted_execution_authority'):
            assert row.get(flag) is False
        self.unavailable(row)

    def custom_profile(self, *, disabled):
        suffix = uuid.uuid4().hex[:16]
        ident, model = 'external-review-' + suffix, 'uninstalled-review-model-' + suffix
        profile = {'provider': 'ollama', 'hosting': 'local', 'endpoint': 'http://127.0.0.1:1',
                   'model': model, 'variant': 'custom', 'supports_tools': False,
                   'vision': False, 'disabled': disabled, 'auto_select': False}
        saved = self.request('PUT', '/workspace/model-profiles/' + ident, profile)
        assert saved.get('id') == ident and saved.get('model') == model
        profiles = self.request('GET', '/workspace/model-profiles')
        assert isinstance(profiles.get('profiles'), list)
        assert any(p.get('id') == ident and p.get('model') == model and p.get('disabled') is disabled for p in profiles['profiles'])
        matches = [row for row in self.discovery()['models'] if row.get('id') == ident]
        assert len(matches) == 1 and matches[0].get('name') == model, 'Discovery must reflect owner-created profiles'
        assert matches[0].get('source') == 'configured_profile'
        assert matches[0].get('available') is False, 'Configured or enabled is not verified inference availability'
        self.unavailable(matches[0])

    def configured_jules(self):
        # Only fresh disposable state, with no jobs and no external network.
        # A saved fake key is a configuration fact, never auth evidence.
        self.request('PUT', '/runtime/policy', {'level': 5})
        settings = self.request('GET', '/integrations/jules/settings')
        saved = self.request('PUT', '/integrations/jules/settings', {
            'enabled': True, 'expected_revision': settings['revision'],
            'allowed_repositories': ['wests-cmd/kingdom'],
            'allowed_sources': ['sources/github/wests-cmd/kingdom'],
            'api_key': 'invalid-disposable-external-review-key'})
        assert saved.get('enabled') is True and saved.get('has_credentials') is True
        row = self.request('GET', '/integrations/adapters/jules/connectivity')
        for flag in ('connected', 'authenticated', 'available_to_planner', 'protocol_verified', 'acp_compliant', 'granted_execution_authority'):
            assert row.get(flag) is False, 'Saved credential presence does not verify provider identity or connectivity'
        self.unavailable(row)

    def run(self):
        operations = (self.unauthenticated, self.forged, self.fresh_readiness, self.jules_unconfigured,
                      lambda: self.custom_profile(disabled=True), lambda: self.custom_profile(disabled=False), self.configured_jules)
        results = []
        for name, operation in zip(CASES, operations):
            try:
                operation()
                results.append({'name': name, 'passed': True, 'detail': 'Fixed external API assertions passed', 'status_code': 200})
            except (AssertionError, ValueError, TypeError, KeyError, OSError):
                # Response text is not copied into trusted diagnostics or counts.
                results.append({'name': name, 'passed': False, 'detail': 'Fixed external API assertion failed', 'status_code': None})
        return results


# Fixed stdlib code, executed by the image's isolated interpreter. Never imports
# candidate modules. Only disposable tmpfs tables and named key files are touched.
STATE_PROBE = r"""
import hashlib,json,sqlite3,sys
from pathlib import Path
assert sys.flags.isolated and sys.flags.no_site
p=Path('/data/data/kingdom.db')
assert p.is_file() and not p.is_symlink()
c=sqlite3.connect(str(p),timeout=2)
tables=('jules_settings','jules_jobs','model_profiles','chatgpt_plan_meta','chatgpt_plan_accounts','chatgpt_plan_pending')
keys=tuple(Path('/data/data/secrets')/name for name in ('vault.key','jules.key','jules-key.lock'))
mode=sys.argv[1]
if mode=='empty':
    # Preflight every fixture before deleting anything.
    for table in tables:
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
            assert c.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0] <= (1 if table in ('jules_settings','chatgpt_plan_meta') else 0)
    for key in keys:
        assert not key.is_symlink()
    for table in tables:
        c.execute('DROP TABLE IF EXISTS "'+table+'"')
    c.commit()
    for key in keys:
        assert not key.is_symlink()
        key.unlink(missing_ok=True)
elif mode=='ready':
    c.execute('CREATE TABLE IF NOT EXISTS chatgpt_plan_meta(id INTEGER PRIMARY KEY,value_json TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS chatgpt_plan_accounts(id TEXT PRIMARY KEY,public_json TEXT NOT NULL,secret BLOB)')
    c.execute('CREATE TABLE IF NOT EXISTS chatgpt_plan_pending(id INTEGER PRIMARY KEY,value BLOB NOT NULL,expires REAL NOT NULL,phase TEXT NOT NULL)')
    meta={'host_id':'urn:uuid:external-review','enabled':True,'model':'gpt-6-sol','active_account':'external-fixture','last_error':None,'revision':1}
    public={'id':'external-fixture','label':'Disposable saved status only','connected':True,'scopes':['resource.invoke','chatgpt.tokens.use.direct'],'expires_at':4102444800,'refresh_state':'idle','refresh_available':False}
    c.execute('INSERT OR REPLACE INTO chatgpt_plan_meta VALUES(1,?)',(json.dumps(meta),))
    c.execute('INSERT OR REPLACE INTO chatgpt_plan_accounts VALUES(?,?,NULL)',('external-fixture',json.dumps(public)))
    c.commit()
elif mode!='snapshot':
    raise ValueError('Unknown fixed probe')
state=[]
for table in tables:
    schema=c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
    rows=list(c.execute('SELECT * FROM "'+table+'" LIMIT 1001')) if schema else []
    assert len(rows)<=1000 and all(len(repr(row))<=65536 for row in rows)
    state.append((table,schema,repr(sorted(rows,key=repr))))
for key in keys:
    assert not key.is_symlink()
    assert not key.exists() or key.stat().st_size<=4096
    state.append((str(key),hashlib.sha256(key.read_bytes()).hexdigest() if key.exists() else None))
print(json.dumps({'sha256':hashlib.sha256(repr(state).encode()).hexdigest()}))
"""


class AdapterOracle(base.ExternalOracle):
    def state_probe(self, mode):
        self.inspect_candidate_container()
        result = subprocess.run(['docker', 'exec', self._container_id, base.PROBE_PYTHON,
                                 '-I', '-S', '-c', STATE_PROBE, mode],
                                capture_output=True, text=True, timeout=10)
        self.inspect_candidate_container()
        if result.returncode or len(result.stdout) > 256:
            raise ValueError('Fixed disposable state probe failed')
        value = json.loads(result.stdout)
        if set(value) != {'sha256'} or not isinstance(value['sha256'], str) or len(value['sha256']) != 64:
            raise ValueError('Invalid fixed state probe envelope')
        return value

    def inventory_read_only(self):
        before = self.state_probe('empty')
        AdapterReadinessSuite(self.transport_fn, self.config['test_auth_token']).discovery()
        assert self.state_probe('snapshot') == before, 'Inventory GET must not initialize tables or keys'

    def unrelated_catalog(self):
        self.state_probe('ready')
        suite = AdapterReadinessSuite(self.transport_fn, self.config['test_auth_token'])
        status = suite.request('GET', '/chatgpt-plan')
        assert status.get('state') == 'ready' and status.get('model') == 'gpt-6-sol'
        rows = [r for r in suite.discovery()['models'] if r.get('id') == 'chatgpt-4o']
        assert len(rows) == 1 and rows[0].get('source') == 'catalog_template'
        assert rows[0].get('available') is False, 'Unrelated selected model cannot make this template available'
        suite.unavailable(rows[0])

    @staticmethod
    def extra_result(name, operation):
        try:
            operation()
            return {'name': name, 'passed': True, 'detail': 'Fixed external state/API assertions passed', 'status_code': 200}
        except (AssertionError, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
            return {'name': name, 'passed': False, 'detail': 'Fixed external state/API assertion failed', 'status_code': None}

    def run_suite(self):
        self.inspect_candidate_container()
        if time.time() >= self.config['deadline_at']:
            raise ValueError('Adapter review window expired')
        read_only = self.extra_result(EXTRA_CASES[0], self.inventory_read_only)
        # This fixed contract requires fresh state, not a copied owner environment.
        profiles = AdapterReadinessSuite(self.transport_fn, self.config['test_auth_token']).request('GET', '/workspace/model-profiles')
        if profiles.get('profiles') != []:
            raise ValueError('Adapter contract requires fresh disposable model state')
        results = AdapterReadinessSuite(self.transport_fn, self.config['test_auth_token']).run()
        results = [read_only, *results, self.extra_result(EXTRA_CASES[1], self.unrelated_catalog)]
        self.inspect_candidate_container()
        if time.time() >= self.config['deadline_at']:
            raise ValueError('Adapter review window expired; no verdict')
        failed = sum(not case['passed'] for case in results)
        record = {'verdict': 'FAILED' if failed else 'PASSED', 'disclaimer': DISCLAIMER,
                  'contract_id': CONTRACT_ID, 'source_revision': self.config['revision'],
                  'candidate_patch_sha256': self.config['candidate_patch_sha256'],
                  'container_image_digest': self.config['image'], 'source_tree_sha256': self.config['source_tree_sha256'],
                  'trusted_test_counts': {'total': len(results), 'passed': len(results)-failed, 'failed': failed},
                  'assertion_results': results, 'timestamp': time.time()}
        return record, self.write_protected_verdict(record)
