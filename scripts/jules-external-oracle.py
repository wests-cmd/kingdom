"""Host-side trusted external behavioral test harness for Kingdom exact-patch review pipeline.

Evaluates candidate API containers through fixed Docker exec + isolated Python
stdlib HTTP probes to the container's loopback API. Candidate responses are
untrusted bounded data. Assertions and test counts remain strictly in this
trusted controller process. Candidate code, tests, plugins, or conftest are NEVER
imported into this harness.
"""
import argparse
import base64
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

DISCLAIMER = (
    "NEGATIVE-FENCE COVERAGE ONLY: This verdict verifies specific security "
    "boundaries and behavioral negative fences. It DOES NOT constitute general "
    "autonomous correctness, functional completeness, or production deployment readiness."
)

PROBE_HELPER_SCRIPT = """import urllib.request, urllib.error, json, sys, base64

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args): return None

url = sys.argv[1]
headers = json.loads(sys.argv[2])
body_data = sys.argv[3].encode('utf-8') if sys.argv[3] else None
method = sys.argv[4]

opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
req = urllib.request.Request(url, data=body_data, headers=headers, method=method)

try:
    with opener.open(req, timeout=5) as resp:
        body = resp.read(65537)
        print(json.dumps({
            'status': resp.status,
            'headers': dict(resp.headers),
            'body': base64.b64encode(body[:65536]).decode('ascii'),
            'truncated': len(body) > 65536
        }))
except urllib.error.HTTPError as e:
    body = e.read(65537)
    print(json.dumps({
        'status': e.code,
        'headers': dict(e.headers) if hasattr(e, 'headers') else {},
        'body': base64.b64encode(body[:65536]).decode('ascii'),
        'truncated': len(body) > 65536
    }))
except Exception as e:
    print(json.dumps({'error': str(e)[:500]}))
"""

SUITE_SPECIFICATION = [
    {
        "id": "api_readiness",
        "description": "API readiness endpoint returns HTTP 200 OK",
        "method": "GET",
        "path": "/health/live",
        "headers": {},
        "body": None,
        "requires_auth": False,
        "expected_status": [200],
    },
    {
        "id": "unauthenticated_rejection",
        "description": "Protected endpoints reject unauthenticated requests with HTTP 401 or 403",
        "method": "GET",
        "path": "/vault/kingdom/documents",
        "headers": {},
        "body": None,
        "requires_auth": False,
        "expected_status": [401, 403],
    },
    {
        "id": "default_off_jules_settings",
        "description": "Jules integration settings route exists and reports enabled=false by default with strict schema",
        "method": "GET",
        "path": "/integrations/jules/settings",
        "headers": {},
        "body": None,
        "requires_auth": True,
        "expected_status": [200],
        "json_check": "jules_settings_schema_check",
    },
    {
        "id": "credential_redaction",
        "description": "API responses do not expose unredacted private keys, secret tokens or vault keys",
        "method": "GET",
        "path": "/diagnostics/full-scan",
        "headers": {},
        "body": None,
        "requires_auth": True,
        "expected_status": [200],
        "redaction_check": True,
    },
    {
        "id": "no_unsigned_acceptance",
        "description": "Document vault rejects unsigned or source-label-only acceptance payloads",
        "method": "POST",
        "path": "/vault/kingdom/documents",
        "headers": {"Content-Type": "application/json"},
        "body": '{"id":"test-doc","body":"acceptance","provenance":{"source":"candidate-source-label"}}',
        "requires_auth": False,
        "expected_status": [401, 403, 422],
    },
    {
        "id": "cancellation_unknown_job",
        "description": "Querying non-existent job or cancellation endpoint handles unknown IDs safely returning 404",
        "method": "GET",
        "path": "/integrations/jules/jobs/nonexistent-job-99999",
        "headers": {},
        "body": None,
        "requires_auth": True,
        "expected_status": [404],
    },
    {
        "id": "unchanged_authorization",
        "description": "Privilege escalation or invalid token attempts are safely rejected with HTTP 401 or 403",
        "method": "GET",
        "path": "/vault/kingdom/documents",
        "headers": {"Authorization": "Bearer invalid-token-forged-role-owner"},
        "body": None,
        "requires_auth": False,
        "expected_status": [401, 403],
    },
]


def calculate_contract_hash(suite_spec=None):
    spec = suite_spec or SUITE_SPECIFICATION
    try:
        script_code = Path(__file__).read_text()
    except Exception:
        script_code = inspect.getsource(ExternalOracle)
    bind_data = {
        "spec": spec,
        "helper": PROBE_HELPER_SCRIPT,
        "controller_implementation": script_code,
    }
    serialized = json.dumps(bind_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


class ExternalOracle:
    def __init__(self, config_filepath, transport_fn=None):
        self.config_path = Path(config_filepath).resolve()
        self.verify_config_permissions(self.config_path)
        self.root = self.config_path.parent
        self.lock_file = (self.root / 'oracle.lock').open('a+b')
        fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.config = json.loads(self.config_path.read_text())
        self.validate_config(self.config)
        self.transport_fn = transport_fn or self.docker_exec_transport

    @staticmethod
    def verify_config_permissions(path):
        if not path.is_file():
            raise ValueError(f"Config file does not exist: {path}")
        stat = path.stat()
        if stat.st_uid != os.getuid() or stat.st_mode & 0o022:
            raise ValueError("Configuration file must be owned by current user and not group/world writable")

    @staticmethod
    def validate_config(c):
        if c.get('repository') != 'wests-cmd/kingdom' or c.get('source') != 'sources/github/wests-cmd/kingdom':
            raise ValueError("Only the owner-approved Kingdom repository is permitted")
        if not re.fullmatch(r'[a-f0-9]{40}', c.get('revision', '')):
            raise ValueError("Pin exact 40-character commit SHA for revision")
        image = c.get('image', '')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            raise ValueError("Pin an exact sha256:64hex container image digest")
        if not isinstance(c.get('container_name'), str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', c['container_name']):
            raise ValueError("Valid container_name is required")
        if type(c.get('deadline_at')) not in (float, int) or c['deadline_at'] < time.time():
            raise ValueError("Deadline must be a valid future timestamp")

    def inspect_candidate_container(self):
        cmd = ['docker', 'inspect', self.config['container_name']]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            raise ValueError(f"Candidate container {self.config['container_name']} not found or docker inspect failed")
        try:
            data = json.loads(res.stdout)
            if not data or not isinstance(data, list):
                raise ValueError("Invalid container inspect data")
            info = data[0]
        except Exception as e:
            raise ValueError(f"Failed to parse container inspect output: {e}")

        # 1. State check
        state = info.get('State', {})
        if not state.get('Running'):
            raise ValueError(f"Candidate container {self.config['container_name']} is not running")

        # 2. Strict Image ID check
        config_image = self.config['image']
        image_id = info.get('Image', '')
        repo_digests = info.get('RepoDigests', [])
        digest_match = any(rd.endswith('@' + config_image) or rd == config_image for rd in repo_digests)
        if image_id != config_image and not digest_match:
            raise ValueError(f"Container image ({image_id}) does not strictly match required sha256 digest ({config_image})")

        # 3. HostConfig Isolation checks
        host_config = info.get('HostConfig', {})

        if host_config.get('NetworkMode') != 'none':
            raise ValueError(f"Container NetworkMode must be 'none', got '{host_config.get('NetworkMode')}'")

        if host_config.get('ReadonlyRootfs') is not True:
            raise ValueError("Container ReadonlyRootfs must be true")

        if host_config.get('Privileged') is True:
            raise ValueError("Container must not be Privileged")

        cap_add = host_config.get('CapAdd')
        if cap_add and len(cap_add) > 0:
            raise ValueError("Container CapAdd must be empty or None")

        # 4. User check (non-root)
        config_obj = info.get('Config', {})
        user = config_obj.get('User', '')
        if not user or user == '0' or user == 'root' or user.startswith('0:'):
            raise ValueError(f"Container must run as non-root user, got '{user}'")

        # 5. Dangerous Mounts check (no docker socket, no secrets, no owner state)
        mounts = info.get('Mounts', [])
        forbidden_mount_patterns = ['docker.sock', '/data/secrets', '/var/lib/kingdom', '/root']
        found_source_mount = False
        for m in mounts:
            dest = m.get('Destination', '')
            source = m.get('Source', '')
            for pattern in forbidden_mount_patterns:
                if pattern in dest or pattern in source:
                    raise ValueError(f"Forbidden mount detected: {source} -> {dest}")
            if dest == '/workspace':
                if m.get('RW') is not False and m.get('Mode') != 'ro':
                    raise ValueError("Workspace mount /workspace must be read-only")
                found_source_mount = True

        if not found_source_mount and self.config.get('require_source_mount', True):
            raise ValueError("Container missing read-only source mount at /workspace")

        # 6. Label checks
        labels = config_obj.get('Labels') or {}
        expected_label_key = self.config.get('expected_label_key', 'kingdom.external-oracle')
        expected_label_val = self.config.get('expected_label_val', self.config['revision'])
        if expected_label_key and labels.get(expected_label_key) != expected_label_val:
            raise ValueError(f"Container missing required label {expected_label_key}={expected_label_val}")

    def docker_exec_transport(self, method, path, headers, body):
        port = self.config.get('api_port', 8012)
        url = f"http://127.0.0.1:{port}{path}"
        headers_json = json.dumps(headers or {})
        body_str = body or ""
        cmd = [
            'docker', 'exec', self.config['container_name'],
            'python3', '-I', '-S', '-c', PROBE_HELPER_SCRIPT,
            url, headers_json, body_str, method
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            raise ValueError(f"Probe transport exec failed with exit code {res.returncode}")
        try:
            out = json.loads(res.stdout.strip())
        except Exception as e:
            raise ValueError("Probe transport returned malformed JSON output")

        if 'error' in out:
            raise ValueError("Probe transport internal execution error")

        if out.get('truncated') is True:
            raise ValueError("Probe response was truncated (>64KB)")

        return out

    def run_suite(self):
        # Enforce local deadline budget
        if time.time() >= self.config['deadline_at']:
            raise ValueError("Local observation deadline exceeded")

        # Inspect container
        if self.transport_fn == self.docker_exec_transport:
            self.inspect_candidate_container()

        results = []
        contract_hash = calculate_contract_hash()
        auth_header = {"Authorization": "Bearer " + self.config.get("test_auth_token", "disposable-test-token")}

        for test in SUITE_SPECIFICATION:
            test_id = test['id']
            method = test['method']
            path = test['path']
            headers = dict(test['headers'])
            if test.get('requires_auth'):
                headers.update(auth_header)
            body = test['body']
            expected_statuses = test['expected_status']

            try:
                resp = self.transport_fn(method, path, headers, body)

                if not isinstance(resp, dict):
                    raise ValueError("Response envelope must be a dictionary")

                if resp.get('truncated') is True:
                    raise ValueError("Response body was truncated")

                status = resp.get('status')
                raw_body_b64 = resp.get('body', '')

                try:
                    body_bytes = base64.b64decode(raw_body_b64.encode('ascii'), validate=True) if raw_body_b64 else b''
                except Exception:
                    raise ValueError("Invalid Base64 body decoding")

                if len(body_bytes) > 65536:
                    raise ValueError("Response body size exceeded 64KB bound")

                body_text = body_bytes.decode('utf-8', errors='replace')

                passed = True
                failure_reasons = []

                if status not in expected_statuses:
                    passed = False
                    failure_reasons.append(f"Expected status in {expected_statuses}, got {status}")

                # Settings Schema Check
                if test.get('json_check') == 'jules_settings_schema_check' and status == 200:
                    try:
                        jdata = json.loads(body_text)
                        if not isinstance(jdata, dict):
                            passed = False
                            failure_reasons.append("Settings response is not a JSON object")
                        else:
                            enabled = jdata.get('enabled')
                            repos = jdata.get('allowed_repositories')
                            sources = jdata.get('allowed_sources')
                            rev = jdata.get('revision')

                            if enabled is not False:
                                passed = False
                                failure_reasons.append(f"Jules settings 'enabled' must be False, got {enabled}")
                            if not isinstance(repos, list):
                                passed = False
                                failure_reasons.append("'allowed_repositories' must be a list")
                            if not isinstance(sources, list):
                                passed = False
                                failure_reasons.append("'allowed_sources' must be a list")
                            if not isinstance(rev, int):
                                passed = False
                                failure_reasons.append("'revision' must be an integer")
                    except Exception as e:
                        passed = False
                        failure_reasons.append(f"Failed settings JSON schema parsing")

                # Credential Redaction Check
                if test.get('redaction_check'):
                    sensitive_patterns = [
                        r'-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----',
                        r'Fernet\([^)]+\)',
                        r'vault_key',
                        r'jules-api\.fernet',
                    ]
                    for pat in sensitive_patterns:
                        if re.search(pat, body_text):
                            passed = False
                            failure_reasons.append("Unredacted sensitive data pattern found in response")

                detail = "PASSED" if passed else "; ".join(failure_reasons)
                results.append({
                    "name": test_id,
                    "passed": passed,
                    "detail": detail,
                    "status_code": status
                })

            except Exception as e:
                results.append({
                    "name": test_id,
                    "passed": False,
                    "detail": f"Probe execution failed: {str(e)}",
                    "status_code": None
                })

        total = len(results)
        passed_count = sum(1 for r in results if r['passed'])
        failed_count = total - passed_count
        overall_verdict = "PASSED" if (total > 0 and failed_count == 0) else "FAILED"

        candidate_patch_sha256 = self.config.get('candidate_patch_sha256', '0'*64)

        verdict_record = {
            "verdict": overall_verdict,
            "disclaimer": DISCLAIMER,
            "source_revision": self.config['revision'],
            "candidate_patch_sha256": candidate_patch_sha256,
            "container_image_digest": self.config['image'],
            "contract_sha256": contract_hash,
            "timestamp": time.time(),
            "trusted_test_counts": {
                "total": total,
                "passed": passed_count,
                "failed": failed_count
            },
            "assertion_results": results
        }

        output_path = self.write_protected_verdict(verdict_record)
        return verdict_record, output_path

    def write_protected_verdict(self, record):
        out_dir = Path(self.config.get('output_dir', self.root)).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        target_path = out_dir / 'oracle_verdict.json'
        tmp_path = target_path.with_suffix('.tmp')

        content = json.dumps(record, indent=2)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(tmp_path, flags, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        tmp_path.replace(target_path)
        dir_fd = os.open(out_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

        return str(target_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Jules External Oracle Behavioral Test Harness")
    parser.add_argument('--config', required=True, help="Path to oracle JSON configuration file")
    args = parser.parse_args()

    oracle = ExternalOracle(args.config)
    record, path = oracle.run_suite()
    print(f"Verdict: {record['verdict']} written to {path}")
    if record['verdict'] != 'PASSED':
        sys.exit(1)
