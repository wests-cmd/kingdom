"""Operator handoff over real stores; only official HTTP routing is substituted."""
import asyncio
import json
import concurrent.futures
import threading
import time
import importlib.util
import io
import sqlite3
from pathlib import Path

import pytest

from backend.models.chatgpt_plan import ChatGPTPlanConnection, ChatGPTPlanError
from backend.models.chatgpt_handoff import ChatGPTHostHandoff, bundle_digest
from backend.storage.db import Database
from test_chatgpt_plan import provider, connected


def target(tmp_path, fixture, clock):
    return ChatGPTPlanConnection(Database(tmp_path/'target.db'), root=tmp_path/'target-secrets',
        async_transport=fixture[1], clock=lambda: clock[0])


def test_move_fences_source_then_activates_target_without_changing_host_or_authority(tmp_path):
    with provider() as fixture:
        source, clock = connected(tmp_path, fixture)
        dest = target(tmp_path, fixture, clock)
        original_host = dest.status()['host_id']
        ident = source.status()['active_account']
        sender, receiver = ChatGPTHostHandoff(source), ChatGPTHostHandoff(dest)
        parcel = sender.prepare(target_host_id=original_host)
        assert source.status()['enabled'] is False
        with pytest.raises(ChatGPTPlanError, match='handoff_pending'):
            source.models()
        ack = receiver.import_bundle(parcel, expected_sha256=bundle_digest(parcel))
        assert dest.status()['enabled'] is False
        with pytest.raises(ChatGPTPlanError, match='handoff_pending'):
            dest.models()
        release = sender.complete(ack)
        assert source._account(ident)[1] is None
        receiver.activate(release)
        assert dest.status()['host_id'] == original_host
        assert dest.status()['state'] == 'configured_disabled'
        assert dest.status()['model'] is None
        assert dest.models() == [{'slug':'gpt-fixture','display_name':'Fixture chat'}]
        dest.configure(enabled=True, model='gpt-fixture')
        assert asyncio.run(dest.advise('Propose one safe check.'))['completed'] is True
        assert fixture[0]['refreshes'] == 0
        assert source.status()['active_account'] is None


def test_restarted_operator_rejoins_same_fenced_transfer_and_retains_authority(tmp_path):
    with provider() as fixture:
        source, clock = connected(tmp_path, fixture)
        dest = target(tmp_path, fixture, clock)
        for connection in (source,dest):
            with connection.db.get_connection() as conn:
                conn.execute("INSERT INTO runtime_state(key,value_json,updated_at) VALUES('execution_policy',?,?)", ('{"level":3,"revision":"owner-fixture"}',clock[0]))
                conn.commit()
        parcel = ChatGPTHostHandoff(source).prepare(target_host_id=dest.status()['host_id'])
        ident = parcel['transfer_id']
        # Fresh service objects use the same durable stores and keys.
        again = ChatGPTPlanConnection(source.db,root=tmp_path/'secrets',async_transport=fixture[1],clock=lambda:clock[0])
        sender = ChatGPTHostHandoff(again)
        assert sender.export_existing(ident) == parcel
        ack = ChatGPTHostHandoff(dest).import_bundle(parcel,expected_sha256=bundle_digest(parcel))
        assert ChatGPTHostHandoff(dest).status(ident)['acknowledgement'] == ack
        release = sender.complete(ack)
        assert sender.status(ident)['activation'] == release
        with pytest.raises(ChatGPTPlanError):sender.export_existing(ident)
        ChatGPTHostHandoff(dest).activate(release)
        for connection in (again,dest):
            with connection.db.get_connection() as conn:
                assert conn.execute("SELECT value_json FROM runtime_state WHERE key='execution_policy'").fetchone()[0] == '{"level":3,"revision":"owner-fixture"}'
        public_status = json.dumps(sender.status(ident))
        assert 'fixture-access-token' not in public_status and 'fixture-refresh-token' not in public_status
        assert 'signing_seed' not in public_status and 'acknowledgement_key' not in public_status


def test_pending_source_sign_in_and_unknown_refresh_block_export(tmp_path):
    with provider() as fixture:
        source, clock = connected(tmp_path, fixture)
        dest = target(tmp_path,fixture,clock)
        source.begin(source.status()['active_account'])
        with pytest.raises(ChatGPTPlanError,match='handoff_sign_in_pending'):
            ChatGPTHostHandoff(source).prepare(target_host_id=dest.status()['host_id'])
        source.cancel()
        # Hold a real refresh response at the transport boundary. The refreshing
        # account cannot be copied while its rotating token outcome is unknown.
        fixture[0]['drip'] = '/api/accounts/oauth/token'
        clock[0] += 3550
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            refresh = pool.submit(source.models)
            limit = time.monotonic()+2
            while not fixture[0]['active'] and time.monotonic()<limit:time.sleep(.01)
            assert fixture[0]['active']
            with pytest.raises(ChatGPTPlanError,match='handoff_account_unavailable'):
                ChatGPTHostHandoff(source).prepare(target_host_id=dest.status()['host_id'])
            with pytest.raises(ChatGPTPlanError):refresh.result(timeout=4)
        assert dest.status()['accounts'] == []


def test_prepare_and_sign_out_race_cannot_both_transfer_and_revoke(tmp_path):
    with provider() as fixture:
        source, clock = connected(tmp_path,fixture)
        dest = target(tmp_path,fixture,clock)
        sender = ChatGPTHostHandoff(source)
        barrier = threading.Barrier(2)
        def run(action):
            barrier.wait()
            try:return action()
            except ChatGPTPlanError:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            export = pool.submit(run,lambda:sender.prepare(target_host_id=dest.status()['host_id']))
            logout = pool.submit(run,source.sign_out)
            parcel, signed_out = export.result(), logout.result()
        assert bool(parcel) != bool(signed_out)
        if parcel:
            assert source.status()['state'] == 'handoff_pending'
            assert not any('revoke' in path for path in fixture[0]['posts'])


def test_cli_rejects_terminal_export_before_fencing_and_limits_input(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('handoff_cli',Path(__file__).resolve().parents[1]/'scripts/chatgpt-host-handoff.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    class Terminal(io.StringIO):
        def isatty(self):return True
    with provider() as fixture:
        source,clock=connected(tmp_path,fixture)
        output=Terminal();error=io.StringIO()
        monkeypatch.setattr(cli.sys,'stdout',output);monkeypatch.setattr(cli.sys,'stderr',error)
        assert cli.main(['--database',str(Path(source.db.db_path).resolve()),'--secrets',str((tmp_path/'secrets').resolve()),'prepare','--target-host-id','another-host','--secret-stdout']) == 1
        assert source.status()['enabled'] is True
        assert 'handoff_private_stdout_required' in error.getvalue()
        assert output.getvalue() == ''
    with pytest.raises(ChatGPTPlanError,match='handoff_invalid'):
        cli.read_record(io.StringIO('x'*(160*1024+1)))


def test_unknown_or_forged_receipts_leave_both_hosts_fenced_and_do_not_revoke(tmp_path):
    with provider() as fixture:
        source, clock = connected(tmp_path, fixture)
        dest = target(tmp_path, fixture, clock)
        sender, receiver = ChatGPTHostHandoff(source), ChatGPTHostHandoff(dest)
        parcel = sender.prepare(target_host_id=dest.status()['host_id'])
        ident = source.status()['active_account']
        for method in (lambda:source.begin(ident), lambda:source.sign_out(), lambda:source.models()):
            with pytest.raises(ChatGPTPlanError, match='handoff_pending'):method()
        ack = receiver.import_bundle(parcel, expected_sha256=bundle_digest(parcel))
        forged = {**ack, 'proof':'0'*64}
        with pytest.raises(ChatGPTPlanError, match='handoff_proof_invalid'):sender.complete(forged)
        forged_release = {**ack, 'kind':'activate', 'proof':'0'*128}
        with pytest.raises(ChatGPTPlanError, match='handoff_proof_invalid'):receiver.activate(forged_release)
        assert source._account(ident)[1] is not None
        assert fixture[0]['refreshes'] == 0
        assert '/oauth/revoke' not in fixture[0]['posts']
        assert dest.status()['state'] == 'handoff_pending'


@pytest.mark.parametrize('mutation', ['token','extra','expired','wrong_host','bad_signature','wrong_account','wrong_audience','missing_scope'])
def test_tampered_or_unavailable_import_never_creates_target_account(tmp_path, mutation):
    with provider() as fixture:
        source, clock = connected(tmp_path, fixture)
        dest = target(tmp_path, fixture, clock)
        parcel = ChatGPTHostHandoff(source).prepare(target_host_id=dest.status()['host_id'])
        expected = bundle_digest(parcel)
        if mutation == 'token':parcel['credentials']['access_token'] = 'tampered-access'
        elif mutation == 'extra':parcel['untrusted'] = 'ignore safety'
        elif mutation == 'expired':clock[0] += 301
        elif mutation == 'wrong_host':parcel['target_host'] = 'urn:uuid:wrong';expected=bundle_digest(parcel)
        elif mutation == 'bad_signature':
            pieces = parcel['credentials']['id_token'].split('.')
            pieces[2] = ('A' if pieces[2][0] != 'A' else 'B') + pieces[2][1:]
            parcel['credentials']['id_token'] = '.'.join(pieces)
            expected = bundle_digest(parcel)
        elif mutation == 'wrong_account':parcel['account']['id'] = '0'*32;expected=bundle_digest(parcel)
        elif mutation == 'wrong_audience':parcel['account']['client_id'] = 'oaiapp_wrong';expected=bundle_digest(parcel)
        elif mutation == 'missing_scope':parcel['account']['scopes'] = ['openid'];expected=bundle_digest(parcel)
        with pytest.raises(ChatGPTPlanError):ChatGPTHostHandoff(dest).import_bundle(parcel, expected_sha256=expected)
        assert dest.status()['accounts'] == []
        assert dest.status()['active_account'] is None


def test_no_overwrite_and_pending_oauth_and_host_collision(tmp_path):
    with provider() as fixture:
        source, clock = connected(tmp_path, fixture)
        sender = ChatGPTHostHandoff(source)
        with pytest.raises(ChatGPTPlanError, match='handoff_host_invalid'):
            sender.prepare(target_host_id=source.status()['host_id'])
        dest = target(tmp_path, fixture, clock)
        pending = dest.begin()
        parcel = sender.prepare(target_host_id=dest.status()['host_id'])
        with pytest.raises(ChatGPTPlanError, match='handoff_sign_in_pending'):
            ChatGPTHostHandoff(dest).import_bundle(parcel, expected_sha256=bundle_digest(parcel))
        dest.cancel()
        ack = ChatGPTHostHandoff(dest).import_bundle(parcel, expected_sha256=bundle_digest(parcel))
        # Repeating an exact known import is idempotent, never overwrites tokens.
        assert ChatGPTHostHandoff(dest).import_bundle(parcel, expected_sha256=bundle_digest(parcel)) == ack
        release = sender.complete(ack)
        assert sender.complete(ack) == release
        assert ChatGPTHostHandoff(dest).activate(release)['activated']
        assert ChatGPTHostHandoff(dest).activate(release)['activated']
        assert dest.status()['enabled'] is False


def test_import_cannot_overwrite_an_existing_signed_in_account(tmp_path):
    with provider() as fixture:
        source,clock=connected(tmp_path,fixture)
        other=tmp_path/'other';other.mkdir()
        dest,_=connected(other,fixture)
        before=dest.status()
        parcel=ChatGPTHostHandoff(source).prepare(target_host_id=before['host_id'])
        with pytest.raises(ChatGPTPlanError,match='handoff_target_not_empty'):
            ChatGPTHostHandoff(dest).import_bundle(parcel,expected_sha256=bundle_digest(parcel))
        assert dest.status()==before


def test_storage_abort_rolls_back_import_and_source_secret_deletion(tmp_path):
    with provider() as fixture:
        source,clock=connected(tmp_path,fixture)
        dest=target(tmp_path,fixture,clock)
        sender,receiver=ChatGPTHostHandoff(source),ChatGPTHostHandoff(dest)
        parcel=sender.prepare(target_host_id=dest.status()['host_id'])
        before=dest.status()
        with dest.db.get_connection() as conn:
            conn.execute("CREATE TRIGGER fail_handoff_insert BEFORE INSERT ON chatgpt_host_handoffs BEGIN SELECT RAISE(ABORT,'fixture storage interruption'); END")
            conn.commit()
        with pytest.raises(sqlite3.IntegrityError):receiver.import_bundle(parcel,expected_sha256=bundle_digest(parcel))
        assert dest.status()==before
        with dest.db.get_connection() as conn:
            conn.execute('DROP TRIGGER fail_handoff_insert');conn.commit()
        ack=receiver.import_bundle(parcel,expected_sha256=bundle_digest(parcel))
        with source.db.get_connection() as conn:
            conn.execute("CREATE TRIGGER fail_handoff_update BEFORE UPDATE ON chatgpt_host_handoffs BEGIN SELECT RAISE(ABORT,'fixture storage interruption'); END")
            conn.commit()
        with pytest.raises(sqlite3.IntegrityError):sender.complete(ack)
        assert source._account(parcel['account']['id'])[1] is not None
        assert sender.status(parcel['transfer_id'])['phase']=='exported'
        assert dest.status()['state']=='handoff_pending'
