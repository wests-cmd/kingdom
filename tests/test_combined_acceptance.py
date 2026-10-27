"""Real signature/SQLite verifier tests, not independent functional execution.

Synthetic fixture declarations exercise only the new unused verifier seam.
"""
import base64
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime import combined_acceptance as combined
from backend.runtime import patch_acceptance
from backend.storage.db import Database


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    key=Ed25519PrivateKey.generate()
    public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    reviewers={'fixture':{'enabled':True,'public_key':public,'projects':['kingdom'],
        'sources':['sources/github/wests-cmd/kingdom'],'contracts':['f'*64], 'combined_contracts':['e'*64]}}
    now=[1000.0]
    records=[];ordered=[]
    for index in (1,2):
        binding=dict(job_id=f'job-{index}',project='kingdom',backlog_id=f'work-{index}',mission_id=f'mission-{index}',
            mission_version=1,step_id='review',source='sources/github/wests-cmd/kingdom',base_revision='a'*40,
            patch_sha256=str(index)*64,contract_sha256='f'*64)
        execution=dict(run_id=f'component-run-{index}',image_sha256='b'*64,source_archive_sha256='c'*64,
            candidate_tree_sha256=str(index)*64,argv=['external-controller','component-fences'],test_count=7,
            failed_count=0,exit_code=0,network_isolated=True,read_only_source=True,verdict_origin='external_controller')
        proof=dict(format='kingdom.patch-test.v2',receipt_id=f'component-{index}',reviewer_id='fixture',
            issued_at=999,expires_at=1600,binding=binding,execution=execution)
        envelope={'payload':proof,'signature':base64.b64encode(key.sign(patch_acceptance.canonical(proof))).decode()}
        records.append({'binding':binding,'attestation':envelope})
        ordered.append(dict(receipt_id=proof['receipt_id'],receipt_sha256=combined.digest(envelope),binding=binding,
                            index=index,reviewer_id='fixture',tree_after_patch_sha256=('d' if index==2 else '1')*64))
    pinned=[{k:entry[k] for k in ('receipt_id','receipt_sha256','binding')} for entry in ordered]
    preparation=dict(format='kingdom.combined-source-preparation.v1',project='kingdom',source='sources/github/wests-cmd/kingdom',
        base_revision='a'*40,source_archive_sha256='c'*64,ordered_inputs=ordered,ordered_inputs_sha256=combined.digest(pinned),
        combined_tree_sha256='d'*64,changed_paths=['a.py','b.py'],scope='Preparation only')
    preparation['provenance_sha256']=combined.digest(preparation)
    contract=dict(contract_id='combined-fixture',contract_sha256='e'*64,minimum_tests=2,
                  argv=['trusted-integration-controller','--combined-tree'])
    binding=combined.expected_binding('programme-a','s1-integration',preparation,contract,records,reviewers,now=now[0])
    execution=dict(run_id='combined-run',image_sha256='b'*64,source_archive_sha256='c'*64,tested_tree_sha256='d'*64,
        argv=contract['argv'],test_count=2,failed_count=0,exit_code=0,network_isolated=True,read_only_source=True,
        verdict_origin='external_combined_controller',cleanup_complete=True)
    proof=dict(format='kingdom.combined-patch-test.v1',receipt_id='combined-receipt',reviewer_id='fixture',issued_at=999,
               expires_at=1500,binding=binding,execution=execution)
    envelope={'payload':proof,'signature':base64.b64encode(key.sign(combined.CONTEXT+combined.canonical(proof))).decode()}
    database=Database(tmp_path/'state.db')
    with database.get_connection() as conn:
        conn.execute('CREATE TABLE current_section(id INTEGER PRIMARY KEY,data TEXT)')
        conn.execute('INSERT INTO current_section VALUES(1,?)',(json.dumps({'preparation':preparation,'contract':contract,'records':records}),))
        conn.commit()
    monkeypatch.setattr(patch_acceptance,'reviewer_registry',lambda:reviewers)
    events=[]
    store=combined.CombinedReceiptStore(database,lambda *args:events.append(args),clock=lambda:now[0])
    def current(conn):
        assert conn.in_transaction
        state=json.loads(conn.execute('SELECT data FROM current_section WHERE id=1').fetchone()[0])
        binding=combined.expected_binding('programme-a','s1-integration',state['preparation'],state['contract'],state['records'],reviewers,now=now[0])
        return binding,state['contract'],state['preparation']
    return dict(key=key,reviewers=reviewers,now=now,records=records,preparation=preparation,contract=contract,
                binding=binding,envelope=envelope,db=database,store=store,current=current,events=events)


def resign(f,envelope):
    envelope['signature']=base64.b64encode(f['key'].sign(combined.CONTEXT+combined.canonical(envelope['payload']))).decode()


def test_separate_combined_verdict_records_without_advancing_any_programme(fixture):
    f=fixture
    assert f['store'].current(f['current']) is None
    record=f['store'].accept(f['envelope'],f['current'])
    assert record['receipt_id']=='combined-receipt'
    assert 'no programme advancement' in record['scope']
    assert f['store'].current(f['current'])['binding']==f['binding']
    assert len(f['events'])==1
    with f['db'].get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM combined_receipts').fetchone()[0]==1
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='work_programmes'").fetchone()


@pytest.mark.parametrize('change',['old_checkout','order','section','contract','argv','empty','failed','cleanup','component_domain','bad_signature'])
def test_changed_combined_claim_cannot_be_recorded_even_with_fresh_signature(fixture,change):
    f=fixture;envelope=copy.deepcopy(f['envelope']);proof=envelope['payload']
    if change=='old_checkout':proof['execution']['tested_tree_sha256']='a'*64
    if change=='order':proof['binding']['ordered_inputs_sha256']='0'*64
    if change=='section':proof['binding']['section_key']='s2-integration'
    if change=='contract':proof['binding']['contract_sha256']='f'*64
    if change=='argv':proof['execution']['argv']=['candidate-prints-pass']
    if change=='empty':proof['execution']['test_count']=0
    if change=='failed':proof['execution']['failed_count']=1
    if change=='cleanup':proof['execution']['cleanup_complete']=False
    if change=='component_domain':proof['format']='kingdom.patch-test.v2'
    resign(f,envelope)
    if change=='bad_signature':envelope['signature']=base64.b64encode(b'x'*64).decode()
    with pytest.raises(ValueError):f['store'].accept(envelope,f['current'])
    assert f['store'].current(f['current']) is None and f['events']==[]


def test_component_signer_scope_alone_is_not_combined_authority(fixture):
    f=fixture;f['reviewers']['fixture'].pop('combined_contracts')
    with pytest.raises(ValueError):f['store'].accept(f['envelope'],f['current'])


def test_consumed_receipts_remain_subject_to_current_expiry_and_revocation(fixture):
    f=fixture;f['store'].accept(f['envelope'],f['current'])
    f['reviewers']['fixture']['enabled']=False
    with pytest.raises(ValueError):f['store'].current(f['current'])
    f['reviewers']['fixture']['enabled']=True;f['now'][0]=1501
    with pytest.raises(ValueError):f['store'].current(f['current'])


def test_changed_current_component_or_preparation_cannot_reuse_record(fixture):
    f=fixture;f['store'].accept(f['envelope'],f['current'])
    with f['db'].get_connection() as conn:
        state=json.loads(conn.execute('SELECT data FROM current_section').fetchone()[0])
        state['records'].reverse()
        conn.execute('UPDATE current_section SET data=?',(json.dumps(state),));conn.commit()
    with pytest.raises(ValueError):f['store'].current(f['current'])


def test_atomic_single_consumption_across_service_instances(fixture):
    f=fixture;other=combined.CombinedReceiptStore(f['db'],lambda *args:None,clock=lambda:f['now'][0])
    def accept(store):
        try:store.accept(f['envelope'],f['current']);return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(accept,[f['store'],other]))==[False,True]
    with pytest.raises(ValueError):other.accept(f['envelope'],f['current'])
    assert other.current(f['current'])['receipt_id']=='combined-receipt'


def test_resolution_and_consumption_hold_sqlite_write_lock(fixture):
    f=fixture
    def locked(conn):
        with sqlite3.connect(f['db'].db_path,timeout=.01) as competitor:
            with pytest.raises(sqlite3.OperationalError):competitor.execute('UPDATE current_section SET data=data')
        return f['current'](conn)
    f['store'].accept(f['envelope'],locked)
