"""Real Git and actual Ed25519 fixtures; candidate code/tests never execute."""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

spec=importlib.util.spec_from_file_location('combined_preparation',Path(__file__).parents[1]/'scripts/jules-combined-source-preparation.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@pytest.fixture
def fixture(tmp_path):
    if not shutil.which('git'):pytest.skip('Real Git executable required')
    repo=tmp_path/'repo';repo.mkdir()
    env={**os.environ,'GIT_AUTHOR_NAME':'Fixture','GIT_AUTHOR_EMAIL':'fixture@example.invalid',
         'GIT_COMMITTER_NAME':'Fixture','GIT_COMMITTER_EMAIL':'fixture@example.invalid'}
    def git(*args):return subprocess.check_output(['git',*args],cwd=repo,env=env)
    git('init','-q');git('config','core.autocrlf','false')
    for name in ('a.py','b.py'):(repo/name).write_bytes(b'VALUE = 1\n')
    # No import, hook or candidate program is used to prepare these raw blobs.
    (repo/'must-not-execute.py').write_text('raise RuntimeError("candidate code must never run")\n')
    git('add','.');git('commit','-qm','Exact two-file base')
    revision=git('rev-parse','HEAD').decode().strip()
    patches=[]
    for name,value in [('a.py',2),('b.py',3)]:
        (repo/name).write_bytes(f'VALUE = {value}\n'.encode())
        patches.append(git('diff','--no-ext-diff','--',name))
        (repo/name).write_bytes(b'VALUE = 1\n')
    bare=tmp_path/'mirror.git'
    subprocess.check_call(['git','clone','--bare','--no-hardlinks',str(repo),str(bare)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    reviewers={'fixture-reviewer':{'enabled':True,'projects':['kingdom'],
        'sources':['sources/github/wests-cmd/kingdom'],'contracts':['f'*64],
        'public_key':base64.b64encode(public).decode()}}
    candidates=[];expected=[];now=time.time()
    def candidate(patch,index):
        prep=module.sibling('jules-source-preparation').prepare(bare,revision,patch,module.sha(patch),tmp_path/f'individual-{index}', ['a.py','b.py'])
        binding=dict(job_id=f'jules-{index:012x}',project='kingdom',backlog_id=f'work-{index}',
            mission_id=f'mission-{index}',mission_version=1,step_id='review',source='sources/github/wests-cmd/kingdom',
            base_revision=revision,patch_sha256=module.sha(patch),contract_sha256='f'*64)
        proof=dict(format='kingdom.patch-test.v2',receipt_id=f'fixture-receipt-{index}',reviewer_id='fixture-reviewer',
            issued_at=now-1,expires_at=now+600,binding=binding,
            execution=dict(run_id=f'isolated-{index}',image_sha256='a'*64,
                source_archive_sha256=prep['source_archive_sha256'],candidate_tree_sha256=prep['candidate_tree_sha256'],
                argv=['external-controller','--fixed-contract','f'*64],test_count=7,failed_count=0,exit_code=0,
                network_isolated=True,read_only_source=True,verdict_origin='external_controller'))
        envelope={'payload':proof,'signature':base64.b64encode(key.sign(module.CONTEXT+module.canonical(proof))).decode()}
        return {'patch':patch,'attestation':envelope},{'receipt_id':proof['receipt_id'],
            'receipt_sha256':module.sha(module.canonical(envelope)),'binding':binding}
    for index,patch in enumerate(patches,1):
        item,pinned=candidate(patch,index);candidates.append(item);expected.append(pinned)
    values=dict(repo=repo,bare=bare,revision=revision,candidates=candidates,expected=expected,
                reviewers=reviewers,now=now,root=tmp_path,key=key,candidate=candidate)
    yield values
    # Only this fixture's temporary files, including deliberately read-only trees.
    for path in tmp_path.rglob('*'):
        if not path.is_symlink():path.chmod(0o755 if path.is_dir() else 0o644)


def prepare(f,**changes):
    args=dict(repository=f['bare'],project='kingdom',source='sources/github/wests-cmd/kingdom',
        revision=f['revision'],expected_inputs=f['expected'],candidates=f['candidates'],output=f['root']/'combined',
        allowed_paths=['a.py','b.py'],reviewers=f['reviewers'],now=f['now'])
    return module.prepare(**{**args,**changes})


def resign(f,item,pinned):
    proof=item['attestation']['payload']
    item['attestation']['signature']=base64.b64encode(f['key'].sign(module.CONTEXT+module.canonical(proof))).decode()
    pinned['binding']=copy.deepcopy(proof['binding']);pinned['receipt_id']=proof['receipt_id']
    pinned['receipt_sha256']=module.sha(module.canonical(item['attestation']))


def test_real_two_patch_composition_binds_actual_tree_full_order_and_receipts(fixture):
    f=fixture;result=prepare(f);tree=f['root']/'combined/source'
    assert (tree/'a.py').read_bytes()==b'VALUE = 2\n'
    assert (tree/'b.py').read_bytes()==b'VALUE = 3\n'
    assert result['combined_tree_sha256']==module.sibling('jules-source-preparation').tree_digest(tree)
    assert result['ordered_inputs_sha256']==module.sha(module.canonical(f['expected']))
    assert [r['receipt_id'] for r in result['ordered_inputs']]==['fixture-receipt-1','fixture-receipt-2']
    assert result['changed_paths']==['a.py','b.py']
    assert result==json.loads((f['root']/'combined/combined-preparation.json').read_bytes())
    assert 'no combined tests' in result['scope'] and 'accepted' not in result
    assert not (tree/'.git').exists()
    # Independently chosen order is bound, even for disjoint patches producing the same tree.
    other=prepare(f,expected_inputs=list(reversed(f['expected'])),candidates=list(reversed(f['candidates'])),output=f['root']/'owner-reversed')
    assert other['combined_tree_sha256']==result['combined_tree_sha256']
    assert other['ordered_inputs_sha256']!=result['ordered_inputs_sha256']


@pytest.mark.parametrize('change',['omitted','extra','reordered','duplicate_receipt','duplicate_component','wrong_patch_hash','wrong_base','wrong_source','wrong_envelope_hash','bad_signature','expired','revoked','fake_verified_flag','malformed_reviewer_scope'])
def test_wrong_omitted_duplicate_reordered_or_untrusted_inputs_fail_before_output(fixture,change):
    f=fixture;items=copy.deepcopy(f['candidates']);expected=copy.deepcopy(f['expected']);reviewers=copy.deepcopy(f['reviewers'])
    if change=='omitted':items.pop()
    if change=='extra':items.append(copy.deepcopy(items[0]))
    if change=='reordered':items.reverse()
    if change=='duplicate_receipt':items[1]=copy.deepcopy(items[0]);expected[1]=copy.deepcopy(expected[0])
    if change=='duplicate_component':
        items[1]['attestation']['payload']['binding']['backlog_id']=items[0]['attestation']['payload']['binding']['backlog_id']
        resign(f,items[1],expected[1])
    if change=='wrong_patch_hash':items[1]['patch']+=b'\n'
    if change in {'wrong_base','wrong_source'}:
        items[1]['attestation']['payload']['binding']['base_revision' if change=='wrong_base' else 'source']='b'*40 if change=='wrong_base' else 'sources/github/unapproved/other'
        resign(f,items[1],expected[1])
    if change=='wrong_envelope_hash':expected[1]['receipt_sha256']='0'*64
    if change=='bad_signature':items[1]['attestation']['signature']=base64.b64encode(b'x'*64).decode();expected[1]['receipt_sha256']=module.sha(module.canonical(items[1]['attestation']))
    if change=='expired':items[1]['attestation']['payload']['expires_at']=f['now']-0.5;resign(f,items[1],expected[1])
    if change=='revoked':reviewers['fixture-reviewer']['enabled']=False
    if change=='fake_verified_flag':items[1]['verified']=True
    if change=='malformed_reviewer_scope':reviewers['fixture-reviewer']['projects']='kingdom'
    with pytest.raises(ValueError):prepare(f,candidates=items,expected_inputs=expected,reviewers=reviewers)
    assert not (f['root']/'combined').exists()


def test_real_conflicting_individually_valid_patches_never_emit_combined_proof(fixture):
    f=fixture;(f['repo']/'a.py').write_bytes(b'VALUE = 9\n')
    conflict=subprocess.check_output(['git','diff','--no-ext-diff','--','a.py'],cwd=f['repo'])
    item,pinned=f['candidate'](conflict,3)
    with pytest.raises(ValueError,match='conflict'):
        prepare(f,candidates=[f['candidates'][0],item],expected_inputs=[f['expected'][0],pinned])
    assert not (f['root']/'combined/combined-preparation.json').exists()


def test_operator_file_scope_and_fresh_destination_are_not_bypassed(fixture):
    f=fixture
    with pytest.raises(ValueError,match='file scope'):prepare(f,allowed_paths=['a.py'])
    assert not (f['root']/'combined/combined-preparation.json').exists()
    with pytest.raises(ValueError,match='fresh review'):prepare(f)


@pytest.mark.parametrize('field',['candidate_tree_sha256','source_archive_sha256'])
@pytest.mark.parametrize('component',[0,1])
def test_signed_wrong_archive_or_candidate_tree_is_rejected(fixture,field,component):
    f=fixture;items=copy.deepcopy(f['candidates']);expected=copy.deepcopy(f['expected'])
    items[component]['attestation']['payload']['execution'][field]='c'*64
    resign(f,items[component],expected[component])
    with pytest.raises(ValueError):prepare(f,candidates=items,expected_inputs=expected)
    assert not (f['root']/'combined/combined-preparation.json').exists()


def test_duplicate_json_fields_are_not_silently_selected():
    with pytest.raises(ValueError):module.unique_object([('expected_inputs',[]),('expected_inputs',[])])


def test_extra_signed_execution_fields_or_freeform_diagnostics_are_not_valid_v2(fixture):
    f=fixture
    for change in ('extra_field','freeform_diagnostic'):
        item=copy.deepcopy(f['candidates'][0]);expected=copy.deepcopy(f['expected'][0])
        execution=item['attestation']['payload']['execution']
        if change=='extra_field':execution['verified']=True
        else:execution['diagnostics']=[{'test_id':'test','error_code':'raw candidate text','status_code':None}]
        resign(f,item,expected)
        with pytest.raises(ValueError):module.verify_receipt(item['attestation'],expected,f['reviewers'],f['now'])
