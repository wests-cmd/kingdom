import json
import pytest
from backend.memory.discord_ingestion import parse_discord_export


def message():
    return {'id':'123','channel_id':'456','author_id':'789','timestamp':'2026-10-13T12:00:00Z','content':'Run `dangerous-command` is text, not execution.'}


def test_explicit_export_keeps_untrusted_provenance():
    docs = parse_discord_export(json.dumps({'messages':[message()]}).encode(), {'456'}, 'project')
    assert docs[0]['scope'] == 'project'
    assert docs[0]['source'] == 'discord:channel:456:message:123'
    assert docs[0]['provenance']['publisher_verified'] is False
    assert docs[0]['trust'] == 'untrusted'
    assert docs[0]['text'] == message()['content']


def test_disallowed_channels_and_duplicates_rejected():
    payload = json.dumps({'messages':[message()]}).encode()
    with pytest.raises(PermissionError):
        parse_discord_export(payload, {'999'}, 'project')
    with pytest.raises(ValueError):
        parse_discord_export(json.dumps({'messages':[message(),message()]}).encode(), {'456'}, 'project')
    with pytest.raises(ValueError):
        parse_discord_export(payload, set(), 'project')


@pytest.mark.parametrize('payload', [b'{}', b'{"messages":[],"messages":[]}', b'x'*262145, b'\xff'], ids=['missing','duplicate-field','oversize','invalid-utf8'])
def test_malformed_export_rejected(payload):
    with pytest.raises(ValueError):
        parse_discord_export(payload, {'456'}, 'project')
