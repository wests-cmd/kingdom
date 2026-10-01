"""Fail the release on known OSV advisories for the installed Python inventory."""
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

from validate_version import get_authoritative_version

import cryptography
from cryptography.hazmat.backends.openssl.backend import backend

packages = sorted([{"name": d.metadata["Name"], "version": d.version}
                   for d in metadata.distributions()], key=lambda p: p["name"].lower())
queries = [{"package": {"name": p["name"], "ecosystem": "PyPI"}, "version": p["version"]}
           for p in packages]
payload = json.dumps({"queries": queries}).encode()
for attempt in range(3):
    try:
        request = Request("https://api.osv.dev/v1/querybatch", data=payload,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=60) as response:
            results = json.load(response)["results"]
        break
    except Exception:
        if attempt == 2:
            raise
        time.sleep(2)
assert len(results) == len(packages)
findings = [{**package, "advisories": [v["id"] for v in result.get("vulns", [])]}
            for package, result in zip(packages, results) if result.get("vulns")]
if findings:
    raise RuntimeError("Known dependency vulnerabilities: " + json.dumps(findings))
assert cryptography.__version__ == "50.0.2"
evidence = {"version": get_authoritative_version(str(Path(__file__).resolve().parents[1])), "platform": sys.platform, "audited": True,
            "audit_source": "https://osv.dev", "checked_at": datetime.now(timezone.utc).isoformat(),
            "cryptography": cryptography.__version__, "openssl": backend.openssl_version_text(),
            "packages": packages, "findings": findings}
Path("evidence").mkdir(exist_ok=True)
Path("evidence/dependencies.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(f"Dependency audit passed: {len(packages)} packages; {evidence['openssl']}")
