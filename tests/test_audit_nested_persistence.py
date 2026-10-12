import json
from backend.security.audit_log import AuditLogger

def test_nested_secrets_and_mixed_keys_are_redacted_on_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = AuditLogger().record('owner', 'test', 'read', 'ALLOWED', 'reviewed', metadata={
        123: 'normal', 'other': [[{'token': 'test-only-secret'}]],
        'headers': [('Authorization', 'Bearer test-only-bearer')],
        'values': ({'password': 'test-only-password'}, {'password=test-only-set'})})
    persisted = (tmp_path/'data/logs/audit.jsonl').read_text()
    assert 'test-only-' not in persisted
    assert json.loads(persisted)['metadata']['123'] == 'normal'
    assert record['metadata']['other'][0][0]['token'] == '******'

def test_circular_audit_metadata_cannot_break_logging(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    items = []; items.append(items)
    AuditLogger().record('owner', 'test', 'read', 'ALLOWED', 'reviewed', metadata={'items': items})
    assert 'circular audit data' in (tmp_path/'data/logs/audit.jsonl').read_text()
