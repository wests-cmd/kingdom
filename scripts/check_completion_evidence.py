#!/usr/bin/env python3
"""Offline, fail-closed validation of Kingdom's release-completion evidence ledger.

This checks record integrity, not the truth of external artifacts or physical tests.
It deliberately does not imply that CI can certify installed-machine security.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "docs" / "completion-evidence.json"
STATUSES = frozenset({
    "NOT_TESTED", "IN_PROGRESS", "CANDIDATE", "NEEDS_EXTERNAL_EVIDENCE",
    "BLOCKED", "VERIFIED"
})
PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
RELEASE_CLASSES = frozenset({"source-candidate", "public-ready", "security-ready"})
PROOF_FIELDS = (
    "source_sha", "evidence_url", "verifier", "platform", "command",
    "expected", "actual", "observed_at", "sha256"
)
IMMUTABLE_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
ITEM_ID = re.compile(r"^[A-Z][A-Z0-9]*-\d{2}$")
SECURITY_IDS = {f"SEC-{i:02d}" for i in range(1, 9)}


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _https(url: object) -> bool:
    if not _string(url):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def _date(value: object, label: str, errors: list[str]) -> None:
    try:
        if not isinstance(value, str):
            raise TypeError
        date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a calendar date YYYY-MM-DD")


def _proof(proof: object, label: str, errors: list[str]) -> None:
    if not isinstance(proof, dict):
        errors.append(f"{label} must be an object")
        return
    for key in PROOF_FIELDS:
        if not _string(proof.get(key)):
            errors.append(f"{label}.{key} must be nonempty")
    if _string(proof.get("source_sha")) and not IMMUTABLE_SHA.fullmatch(proof["source_sha"]):
        errors.append(f"{label}.source_sha must be an immutable 40-character Git SHA")
    if _string(proof.get("sha256")) and not SHA256.fullmatch(proof["sha256"]):
        errors.append(f"{label}.sha256 must be 64 hex characters")
    if _string(proof.get("evidence_url")) and not _https(proof["evidence_url"]):
        errors.append(f"{label}.evidence_url must be https")
    if _string(proof.get("observed_at")):
        try:
            datetime.fromisoformat(proof["observed_at"].replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{label}.observed_at must be ISO 8601")


def validate(ledger: object) -> list[str]:
    """Return all schema/consistency errors rather than raising or claiming proof."""
    errors: list[str] = []
    if not isinstance(ledger, dict):
        return ["ledger must be a JSON object"]
    if type(ledger.get("schema_version")) is not int or ledger["schema_version"] != 1:
        errors.append("schema_version must equal integer 1")
    _date(ledger.get("as_of"), "as_of", errors)
    classification = ledger.get("release_classification")
    if classification not in RELEASE_CLASSES:
        errors.append(f"unknown release_classification: {classification!r}")
    if not _string(ledger.get("description")):
        errors.append("description must be nonempty")
    items = ledger.get("items")
    if not isinstance(items, list) or not items:
        return errors + ["items must be a nonempty list"]

    seen: set[str] = set()
    deps: dict[str, list[str]] = {}
    item_by_id: dict[str, dict] = {}
    for number, item in enumerate(items):
        label = f"items[{number}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ITEM_ID.fullmatch(ident):
            errors.append(f"{label}.id must match an ID like SEC-01")
            continue
        if ident in seen:
            errors.append(f"duplicate id: {ident}")
            continue
        seen.add(ident)
        item_by_id[ident] = item
        for field in ("title", "area", "acceptance"):
            if not _string(item.get(field)):
                errors.append(f"{ident}.{field} must be nonempty")
        if item.get("priority") not in PRIORITIES:
            errors.append(f"{ident}.priority invalid")
        if item.get("status") not in STATUSES:
            errors.append(f"{ident}.status invalid")
        if not _https(item.get("source")):
            errors.append(f"{ident}.source must be an https provenance URL")
        dependencies = item.get("dependencies")
        if not isinstance(dependencies, list) or not all(isinstance(dep, str) for dep in dependencies):
            errors.append(f"{ident}.dependencies must be a string list")
            dependencies = []
        if len(set(dependencies)) != len(dependencies):
            errors.append(f"{ident}.dependencies repeats an ID")
        deps[ident] = dependencies
        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{ident}.evidence must be a list")
            evidence = []
        for index, proof in enumerate(evidence):
            _proof(proof, f"{ident}.evidence[{index}]", errors)
        if item.get("status") == "VERIFIED" and not evidence:
            errors.append(f"{ident}: VERIFIED requires attributable immutable evidence")
        if ident in SECURITY_IDS and item.get("area") != "installed-security":
            errors.append(f"{ident}: installed security gate cannot be reclassified")
    absent = SECURITY_IDS - seen
    if absent:
        errors.append("missing independent security gates: " + ", ".join(sorted(absent)))
    for ident, dependencies in deps.items():
        for dep in dependencies:
            if dep not in seen:
                errors.append(f"{ident} has unknown dependency {dep}")

    # A cyclic dependency would make the next action permanently ambiguous.
    visited: set[str] = set()
    active: set[str] = set()

    def visit(ident: str) -> None:
        if ident in active:
            errors.append(f"dependency cycle includes {ident}")
            return
        if ident in visited:
            return
        active.add(ident)
        for dep in deps.get(ident, ()):
            if dep in deps:
                visit(dep)
        active.remove(ident)
        visited.add(ident)

    for ident in deps:
        visit(ident)

    if classification == "security-ready":
        pending = sorted(ident for ident in SECURITY_IDS
                         if item_by_id.get(ident, {}).get("status") != "VERIFIED")
        if pending:
            errors.append("security-ready claimed with unverified independent gates: " + ", ".join(pending))
    # Security-ready is stronger than public-ready, not an alternative route
    # around outstanding release-critical work.
    for ident, dependencies in deps.items():
        if item_by_id[ident].get("status") == "VERIFIED":
            unresolved = sorted(dep for dep in dependencies
                                if dep in item_by_id and item_by_id[dep].get("status") != "VERIFIED")
            if unresolved:
                errors.append(f"{ident}: VERIFIED with unresolved dependencies: " + ", ".join(unresolved))
    if classification in {"public-ready", "security-ready"}:
        pending = sorted(ident for ident, item in item_by_id.items()
                         if item.get("priority") in {"P0", "P1"} and item.get("status") != "VERIFIED")
        if pending:
            errors.append(f"{classification} claimed with unresolved P0/P1 work: " + ", ".join(pending))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args(argv)
    try:
        with args.file.open(encoding="utf-8") as stream:
            ledger = json.load(stream)
    except (OSError, ValueError) as exc:
        print(f"COMPLETION LEDGER FAIL: {exc}", file=sys.stderr)
        return 1
    errors = validate(ledger)
    if errors:
        for error in errors:
            print(f"COMPLETION LEDGER FAIL: {error}", file=sys.stderr)
        return 1
    items = ledger["items"]
    unverified = sum(row["status"] != "VERIFIED" for row in items)
    print(f"COMPLETION LEDGER VALID: {len(items)} claims, {unverified} not verified; "
          f"release_classification={ledger['release_classification']}")
    print("This is schema integrity ONLY, not independent security or installed-runtime certification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
