"""All fixtures are offline. A failed audit must block before installation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_known_compromises.py"
spec = importlib.util.spec_from_file_location("known_compromises", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AdvisoryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for p in audit.PYTHON:
            self.write(p, "# empty\n")
        for p in audit.NPM:
            self.write(p, json.dumps({"dependencies": {}}))
        for p in audit.LOCKS:
            self.write(p, json.dumps({"lockfileVersion": 3, "packages": {}}))

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_clean_inventory(self):
        self.assertEqual(audit.scan(self.root)["status"], "no_known_matches")

    def test_malicious_python_startup_hook_versions(self):
        for value in ("1.26.1", "1.26.2"):
            self.write("requirements.txt", "agent_framework==" + value)
            self.assertEqual(audit.scan(self.root)["status"], "blocked")
        self.write("requirements.txt", "agent-framework==1.26.0")
        self.assertEqual(audit.scan(self.root)["status"], "no_known_matches")

    def test_unpinned_is_not_safe(self):
        self.write("requirements.txt", "agent-framework>=1.20")
        self.assertEqual(audit.scan(self.root)["status"], "blocked")

    def test_nested_git_server_requirement(self):
        self.write("requirements.txt", "-r configs/mcp.txt")
        self.write("configs/mcp.txt", "mcp-server-git==2026.11.11")
        self.assertEqual(audit.scan(self.root)["status"], "blocked")
        self.write("configs/mcp.txt", "mcp-server-git==2026.11.18")
        self.assertEqual(audit.scan(self.root)["status"], "no_known_matches")

    def test_gateway_requires_ssrf_fix_not_only_admin_fix(self):
        self.write("requirements-release.txt", "mcp-gateway-registry==1.25.0")
        self.assertEqual(audit.scan(self.root)["status"], "blocked")
        self.write("requirements-release.txt", "mcp-gateway-registry==1.35.0")
        self.assertEqual(audit.scan(self.root)["status"], "no_known_matches")

    def test_npm_direct_and_transitive_malware(self):
        self.write("frontend/package.json", json.dumps({"dependencies": {"mem0-mcp-server": "^1.0"}}))
        self.assertEqual(audit.scan(self.root)["status"], "blocked")
        self.write("frontend/package.json", '{"dependencies":{}}')
        self.write("desktop/package-lock.json", json.dumps({"packages": {
            "node_modules/nested/node_modules/mem0-mcp-server": {"version": "0.0.1"}}}))
        self.assertEqual(audit.scan(self.root)["status"], "blocked")

    def test_editable_vcs_egg_cannot_hide_compromised_python_package(self):
        self.write("requirements.txt", "-e git+https://example.test/repo#egg=agent-framework")
        with self.assertRaises(ValueError):
            audit.scan(self.root)

    def test_npm_alias_cannot_hide_malicious_plugin(self):
        self.write("desktop/package.json",
                   json.dumps({"dependencies": {"innocent-name": "npm:mem0-mcp-server@0.0.1"}}))
        self.assertEqual(audit.scan(self.root)["status"], "blocked")

    def test_lockfile_declared_actual_name_takes_precedence_over_alias(self):
        self.write("frontend/package-lock.json",
                   json.dumps({"packages": {"node_modules/alias": {
                       "name": "mem0-mcp-server", "version": "0.0.1"}}}))
        self.assertEqual(audit.scan(self.root)["status"], "blocked")

    def test_local_installer_audits_before_any_package_execution(self):
        installer = (SCRIPT.parents[1] / "scripts/install.sh").read_text(encoding="utf-8")
        audit_at = installer.index("python3 scripts/audit_known_compromises.py")
        pip_at = installer.index("pip install")
        npm_at = installer.index("npm ci")
        self.assertLess(audit_at, pip_at)
        self.assertLess(audit_at, npm_at)
        self.assertNotIn("npm install", installer)

    def test_missing_manifest_is_a_failing_audit(self):
        (self.root / "frontend/package-lock.json").unlink()
        with self.assertRaises(ValueError):
            audit.scan(self.root)


if __name__ == "__main__":
    unittest.main()
