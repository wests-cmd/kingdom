import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('jules_oracle', Path(__file__).parents[1] / 'scripts/jules-external-oracle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config_path = self.root / 'oracle_config.json'
        self.valid_config = {
            "repository": "wests-cmd/kingdom",
            "source": "sources/github/wests-cmd/kingdom",
            "revision": "2c28b5b9dd4595b3a5669467a75c9e7089219733",
            "image": "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "container_name": "test-candidate-container",
            "deadline_at": time.time() + 3600,
            "candidate_patch_sha256": "a" * 64,
            "output_dir": str(self.root / 'output'),
            "require_source_mount": False
        }
        self.write_config(self.valid_config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_config(self, cfg):
        content = json.dumps(cfg)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(self.config_path, flags, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(content)

    def test_candidate_modules_never_imported(self):
        forbidden_modules = ['candidate_app', 'candidate_code', 'conftest']
        for mod in forbidden_modules:
            self.assertNotIn(mod, sys.modules)

    def test_routes_use_integrations_jules_path(self):
        paths = [spec['path'] for spec in module.SUITE_SPECIFICATION]
        self.assertIn('/integrations/jules/settings', paths)
        self.assertIn('/integrations/jules/jobs/nonexistent-job-99999', paths)
        self.assertNotIn('/api/jules/settings', paths)

    def test_missing_endpoint_or_404_on_required_settings_fails(self):
        def mock_404_transport(method, path, headers, body):
            return {"status": 404, "body": base64.b64encode(b'Not Found').decode('ascii')}

        oracle = module.ExternalOracle(self.config_path, transport_fn=mock_404_transport)
        record, path = oracle.run_suite()
        self.assertEqual(record['verdict'], 'FAILED')

    def test_malformed_json_settings_response_fails(self):
        def mock_malformed_settings(method, path, headers, body):
            if path == '/integrations/jules/settings':
                return {"status": 200, "body": base64.b64encode(b'NOT_VALID_JSON{').decode('ascii')}
            elif path == '/health/live':
                return {"status": 200, "body": base64.b64encode(b'{}').decode('ascii')}
            return {"status": 401, "body": b''}

        oracle = module.ExternalOracle(self.config_path, transport_fn=mock_malformed_settings)
        record, path = oracle.run_suite()
        self.assertEqual(record['verdict'], 'FAILED')
        res = next(r for r in record['assertion_results'] if r['name'] == 'default_off_jules_settings')
        self.assertFalse(res['passed'])

    def test_settings_enabled_true_or_missing_fields_fails(self):
        def mock_enabled_true(method, path, headers, body):
            if path == '/integrations/jules/settings':
                return {"status": 200, "body": base64.b64encode(b'{"enabled": true}').decode('ascii')}
            return {"status": 200, "body": b''}

        oracle = module.ExternalOracle(self.config_path, transport_fn=mock_enabled_true)
        record, path = oracle.run_suite()
        res = next(r for r in record['assertion_results'] if r['name'] == 'default_off_jules_settings')
        self.assertFalse(res['passed'])

    def test_truncated_response_fails(self):
        def mock_truncated_transport(method, path, headers, body):
            return {"status": 200, "body": base64.b64encode(b'{}').decode('ascii'), "truncated": True}

        oracle = module.ExternalOracle(self.config_path, transport_fn=mock_truncated_transport)
        record, path = oracle.run_suite()
        self.assertEqual(record['verdict'], 'FAILED')

    def test_successful_mock_transport_passes_suite(self):
        def mock_passing_transport(method, path, headers, body):
            if path == '/health/live':
                return {"status": 200, "body": base64.b64encode(b'{"status":"ok"}').decode('ascii')}
            elif path == '/vault/kingdom/documents':
                return {"status": 401, "body": base64.b64encode(b'{"detail":"Unauthorized"}').decode('ascii')}
            elif path == '/integrations/jules/settings':
                valid_settings = {
                    "enabled": False,
                    "allowed_repositories": [],
                    "allowed_sources": [],
                    "revision": 1
                }
                return {"status": 200, "body": base64.b64encode(json.dumps(valid_settings).encode()).decode('ascii')}
            elif path == '/diagnostics/full-scan':
                return {"status": 200, "body": base64.b64encode(b'{"status":"clean"}').decode('ascii')}
            elif path.startswith('/integrations/jules/jobs/'):
                return {"status": 404, "body": base64.b64encode(b'{"detail":"Not found"}').decode('ascii')}
            return {"status": 401, "body": b''}

        oracle = module.ExternalOracle(self.config_path, transport_fn=mock_passing_transport)
        record, path = oracle.run_suite()
        self.assertEqual(record['verdict'], 'PASSED')
        self.assertEqual(record['trusted_test_counts']['passed'], len(module.SUITE_SPECIFICATION))

    def test_invalid_image_digest_format_rejected(self):
        cfg = dict(self.valid_config)
        cfg['image'] = 'sha256:short'
        self.write_config(cfg)
        with self.assertRaisesRegex(ValueError, "Pin an exact sha256:64hex container image digest"):
            module.ExternalOracle(self.config_path)

    def test_inspect_container_rejects_non_isolated_containers(self):
        oracle = module.ExternalOracle(self.config_path, transport_fn=lambda *a: {})

        # Test NetworkMode != none
        mock_inspect = [{
            "State": {"Running": True},
            "Image": self.valid_config['image'],
            "HostConfig": {"NetworkMode": "bridge", "ReadonlyRootfs": True, "Privileged": False},
            "Config": {"User": "1000:1000", "Labels": {"kingdom.external-oracle": self.valid_config['revision']}}
        }]

        original_run = module.subprocess.run
        def fake_run(cmd, capture_output=True, text=True, timeout=10):
            if cmd[:2] == ['docker', 'inspect']:
                class Resp:
                    returncode = 0
                    stdout = json.dumps(mock_inspect)
                return Resp()
            return original_run(cmd, capture_output=capture_output, text=text, timeout=timeout)

        module.subprocess.run = fake_run
        try:
            with self.assertRaisesRegex(ValueError, "NetworkMode must be 'none'"):
                oracle.inspect_candidate_container()
        finally:
            module.subprocess.run = original_run

    def test_protected_output_verdict_writing_and_permissions(self):
        def mock_passing_transport(method, path, headers, body):
            if path == '/health/live': return {"status": 200, "body": b''}
            if path == '/integrations/jules/settings':
                return {"status": 200, "body": base64.b64encode(b'{"enabled":false,"allowed_repositories":[],"allowed_sources":[],"revision":1}').decode('ascii')}
            if path == '/diagnostics/full-scan': return {"status": 200, "body": b''}
            if path.startswith('/integrations/jules/jobs/'): return {"status": 404, "body": b''}
            return {"status": 401, "body": b''}

        oracle = module.ExternalOracle(self.config_path, transport_fn=mock_passing_transport)
        record, path_str = oracle.run_suite()

        output_path = Path(path_str)
        self.assertTrue(output_path.is_file())
        if os.name != 'nt':
            stat = output_path.stat()
            self.assertEqual(stat.st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
