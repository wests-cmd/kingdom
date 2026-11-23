"""Regression tests: progress labels cannot replace independent release evidence."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.check_completion_evidence import DEFAULT_LEDGER, validate, main


@pytest.fixture
def ledger():
    return json.loads(DEFAULT_LEDGER.read_text(encoding="utf-8"))


def _get(ledger, ident="SEC-01"):
    return next(item for item in ledger["items"] if item["id"] == ident)


def _valid_proof():
    return {
        "source_sha": "a" * 40,
        "evidence_url": "https://github.com/wests-cmd/kingdom/actions/runs/123456",
        "verifier": "independent reviewer",
        "platform": "Windows x64 installed app",
        "command": "python tests/installed_security_gate.py",
        "expected": "revoked identity is denied",
        "actual": "verified deny with signed logs",
        "observed_at": "2026-11-22T22:17:00-08:00",
        "sha256": "b" * 64,
    }


def test_repo_ledger_is_well_formed_but_not_certified(ledger):
    assert not validate(ledger)
    assert ledger["release_classification"] == "source-candidate"
    for i in range(1, 9):
        assert _get(ledger, f"SEC-{i:02d}")["status"] != "VERIFIED"
    assert main(["--file", str(DEFAULT_LEDGER)]) == 0


def test_duplicate_id_rejected(ledger):
    ledger["items"].append(deepcopy(ledger["items"][0]))
    assert any("duplicate id" in error for error in validate(ledger))


def test_missing_security_gate_rejected(ledger):
    ledger["items"] = [i for i in ledger["items"] if i["id"] != "SEC-08"]
    assert any("missing independent security gates" in e for e in validate(ledger))


def test_claimed_verification_without_evidence_is_rejected(ledger):
    _get(ledger)["status"] = "VERIFIED"
    assert any("VERIFIED requires attributable immutable evidence" in e for e in validate(ledger))


def test_fake_evidence_sha_rejected(ledger):
    row = _get(ledger)
    row["status"] = "VERIFIED"
    row["evidence"] = [_valid_proof()]
    row["evidence"][0]["source_sha"] = "main"
    assert any("immutable 40-character Git SHA" in e for e in validate(ledger))


def test_proof_without_independent_verifier_rejected(ledger):
    row = _get(ledger)
    row["status"] = "VERIFIED"
    row["evidence"] = [_valid_proof()]
    row["evidence"][0]["verifier"] = ""
    assert any("verifier must be nonempty" in e for e in validate(ledger))


def test_evidence_without_https_rejected(ledger):
    row = _get(ledger)
    row["status"] = "VERIFIED"
    row["evidence"] = [_valid_proof()]
    row["evidence"][0]["evidence_url"] = "file:///tmp/fabricated-pass.txt"
    assert any("evidence_url must be https" in e for e in validate(ledger))


def test_valid_scoped_proof_is_accepted_without_global_release_promotion(ledger):
    row = _get(ledger)
    row["status"] = "VERIFIED"
    row["evidence"] = [_valid_proof()]
    assert not validate(ledger)
    assert ledger["release_classification"] == "source-candidate"


def test_security_ready_requires_all_eight_independent_gates(ledger):
    ledger["release_classification"] = "security-ready"
    assert any("unverified independent gates" in e for e in validate(ledger))


def test_public_ready_requires_all_p0_p1_items(ledger):
    ledger["release_classification"] = "public-ready"
    assert any("unresolved P0/P1 work" in e for e in validate(ledger))


def test_dependency_cycle_rejected(ledger):
    _get(ledger, "CORE-01")["dependencies"] = ["RUNTIME-01"]
    assert any("dependency cycle" in e for e in validate(ledger))


def test_unknown_dependency_rejected(ledger):
    _get(ledger)["dependencies"] = ["DOES-NOT-EXIST"]
    assert any("unknown dependency" in e for e in validate(ledger))


def test_gate_cannot_be_recategorized_as_nonsecurity(ledger):
    _get(ledger)["area"] = "release-completion"
    assert any("cannot be reclassified" in e for e in validate(ledger))


def test_missing_and_bad_json_fail_closed(tmp_path):
    assert main(["--file", str(tmp_path / "absent.json")]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert main(["--file", str(bad)]) == 1


def test_invalid_date_and_status_rejected(ledger):
    ledger["as_of"] = "not a date"
    _get(ledger)["status"] = "DONE"
    result = validate(ledger)
    assert any("calendar date" in e for e in result)
    assert any(".status invalid" in e for e in result)


def test_ledger_path_is_project_owned():
    assert DEFAULT_LEDGER.relative_to(Path(__file__).resolve().parents[1]).as_posix() == "docs/completion-evidence.json"
