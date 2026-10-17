from types import SimpleNamespace
import pytest
from backend.skills.documents import SkillDocumentService, parse_document, export_document
from backend.skills.portable import parse_map
from backend.storage.db import Database
from backend.storage.integration_repository import IntegrationRepository

CONTENT = '---\nname: repo-review\ndescription: Review a repository\nallowed-tools: [Bash]\n---\nRead https://example.com and run `git diff` after authorization.\n'


def test_markdown_is_inert_and_harness_neutral():
    document = parse_document(CONTENT, "discord:attachment-42", "claude")
    assert document.execution_enabled is False
    assert document.trust == "untrusted"
    assert document.provenance.harness == "claude"
    assert "allowed-tools" not in export_document(document)
    assert parse_document(export_document(document)).instructions == document.instructions
    # Existing preferences boundary must not become an instruction upload bypass.
    with pytest.raises(ValueError):
        parse_map("skill.json", b'{"schema_version":"1.0","map_id":"x","metadata":{"description":"run `git diff`"}}')


@pytest.mark.parametrize("content", [
    '---\nname: a\nname: b\ndescription: x\n---\nx',
    '---\nname: ../escape\ndescription: x\n---\nx',
    '---\nname: &a test\ndescription: *a\n---\nx',
    '---\nname: test\ndescription: x\n---\n',
    CONTENT + '\x00',
])
def test_reject_ambiguous_or_invalid_documents(content):
    with pytest.raises(ValueError):
        parse_document(content)


def test_persistent_confirmation_is_actor_bound_and_single_use(tmp_path):
    repo = IntegrationRepository(Database(tmp_path / "skills.db"))
    events = []
    authorized = []
    portable = SimpleNamespace(repository=repo,
        authorize=lambda actor, capability: authorized.append((actor, capability)),
        engine=SimpleNamespace(events=SimpleNamespace(publish=lambda *args: events.append(args))))
    service = SkillDocumentService(portable)
    preview = service.preview("owner", CONTENT, harness="hermes")
    with pytest.raises(PermissionError):
        service.confirm("other", preview["preview_id"], preview["checksum"])
    result = service.confirm("owner", preview["preview_id"], preview["checksum"])
    assert result["state"] == "saved_untrusted_context"
    with pytest.raises(PermissionError):
        service.confirm("owner", preview["preview_id"], preview["checksum"])
    restored = SkillDocumentService(portable).export("owner", "repo-review")
    assert restored["document"]["execution_enabled"] is False
    assert restored["document"]["provenance"]["harness"] == "hermes"
    with pytest.raises(KeyError):
        service.export("other", "repo-review")
    assert ("owner", "export_skillmaps") in authorized
    assert events[-1][0] == "skill_document.imported"
