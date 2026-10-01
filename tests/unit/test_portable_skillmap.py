import json
from pathlib import Path
import pytest
from backend.skills.portable import parse_map, canonical_map, map_checksum

FIXTURE = Path(__file__).parents[1] / "fixtures/product-research.skillmap.json"


def test_canonical_export_reimport_equivalence():
    original = parse_map(FIXTURE.name, FIXTURE.read_bytes())
    payload = canonical_map(original)
    again = parse_map("export.json", payload)
    assert canonical_map(again) == payload
    assert map_checksum(again) == map_checksum(original)
    original.metadata.created_at = "2026-09-30"
    assert map_checksum(original) == map_checksum(again)


@pytest.mark.parametrize("filename,payload", [
    ("../map.json", b"{}"), ("C:\\map.json", b"{}"), ("map.exe", b"{}"),
    ("map.json", b"x" * 262145), ("map.json", b'{"map_id":"a","map_id":"b"}'),
    ("map.yaml", b"a: &a [*a]"), ("map.yaml", b"!!python/object/apply:os.system [whoami]"),
    ("map.json", b"{"), ("map.json", b"\xff"),
], ids=["traversal", "absolute", "extension", "oversize", "duplicate", "alias", "tag", "broken", "encoding"])
def test_malicious_and_malformed_upload_rejected(filename, payload):
    with pytest.raises(ValueError):
        parse_map(filename, payload)


@pytest.mark.parametrize("field,value", [("schema_version", "2.0"), ("permissions", ["system.admin"]),
                                          ("endpoint", "https://localhost"), ("capabilities", ["../../etc"]),
                                          ("metadata", {"title": "password=supersecret"}),
                                          ("metadata", {"title": "def attack(): return 1"})])
def test_no_grants_secrets_executable_code_or_endpoints(field, value):
    data = json.loads(FIXTURE.read_text())
    data[field] = value
    with pytest.raises(ValueError):
        parse_map("map.json", json.dumps(data).encode())
