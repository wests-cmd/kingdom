"""Catalog metadata is not an execution grant or an independent test verdict."""
import asyncio
import base64
import copy
import json
import os
from pathlib import Path
import time

import pytest

from backend.runtime import independent_contract_catalog as catalog
from backend.runtime import patch_acceptance
from backend.runtime.work_programmes import WorkProgrammes
from backend.runtime.missions import MissionPlan
from test_project_test_missions import runtime
from test_project_test_missions import plan as local_test_plan


def manifest():
    return {'version':1, 'contracts':[{
        'contract_id':'api-negative-fences', 'contract_sha256':'b'*64,
        'project':'kingdom', 'source':'sources/github/wests-cmd/kingdom',
        'base_revisions':['a'*40], 'minimum_tests':7, 'expires_at':time.time()+600,
        'description':'Seven fixed API negative fences',
        'coverage_limits':['No generic functional correctness or returned-patch integration proof'],
    }]}


def reviewers():
    return {'fixture-reviewer':{'enabled':True, 'projects':['kingdom'],
        'sources':['sources/github/wests-cmd/kingdom'], 'contracts':['b'*64],
        'public_key':base64.b64encode(b'x'*32).decode()}}


def install_test_seams(monkeypatch, data=None, registry=None):
    data = manifest() if data is None else data
    registry = reviewers() if registry is None else registry
    monkeypatch.setattr(catalog, '_read_manifest', lambda:copy.deepcopy(data))
    monkeypatch.setattr(patch_acceptance, 'reviewer_registry', lambda:copy.deepcopy(registry))


def descriptor():
    return {'project':'kingdom', 'source':'sources/github/wests-cmd/kingdom',
        'base_revision':'a'*40, 'contract_id':'api-negative-fences',
        'contract_sha256':'b'*64, 'minimum_tests':7}


def test_exact_descriptor_current_registration_and_limits_are_discovery_only(monkeypatch):
    install_test_seams(monkeypatch)
    result=catalog.discover_contracts('kingdom',base_revision='a'*40)
    assert result['status']=='available'
    assert result['contracts'][0]['descriptor']==descriptor()
    assert result['contracts'][0]['registered_reviewers']==['fixture-reviewer']
    assert 'not task-specific adequacy' in result['scope']
    assert not any(key in result for key in ('approval','enabled','grants','accepted'))
    assert catalog.discover_contracts('centipede',base_revision='a'*40)['contracts']==[]
    assert catalog.discover_contracts('kingdom',source='sources/github/wests-cmd/other',base_revision='a'*40)['contracts']==[]
    assert catalog.discover_contracts('kingdom',base_revision='c'*40)['contracts']==[]


@pytest.mark.parametrize('change',['altered_hash','expired','disabled_reviewer','unregistered_hash','malformed_scope','invalid_key','extra_manifest_field','boolean_version'])
def test_altered_stale_invalid_or_unregistered_entries_are_never_available(monkeypatch,change):
    data,registry=manifest(),reviewers()
    if change=='altered_hash':data['contracts'][0]['contract_sha256']='c'*64
    if change=='expired':data['contracts'][0]['expires_at']=time.time()-1
    if change=='disabled_reviewer':registry['fixture-reviewer']['enabled']=False
    if change=='unregistered_hash':registry['fixture-reviewer']['contracts']=['c'*64]
    if change=='malformed_scope':registry['fixture-reviewer']['sources']='sources/github/wests-cmd/kingdom'
    if change=='invalid_key':registry['fixture-reviewer']['public_key']='invalid!'
    if change=='extra_manifest_field':data['grant_process_execute']=True
    if change=='boolean_version':data['version']=True
    install_test_seams(monkeypatch,data,registry)
    result=catalog.discover_contracts('kingdom',base_revision='a'*40)
    assert result['status']!='available' and result['contracts']==[]


def test_unavailable_manifest_does_not_prevent_existing_plain_language_planning(runtime,monkeypatch):
    def unavailable():raise ValueError('Protected operator configuration unavailable')
    monkeypatch.setattr(catalog,'_read_manifest',unavailable)
    engine,backlog,_=runtime
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','catalog-unavailable','Work:\n- Check existing task',
        source_revision='a'*40,planner_mode='chatgpt')
    result=asyncio.run(service.plan_next(state['id'],state['revision']))
    row=result['sections'][0]['items'][0]
    assert row['planning']=='awaiting_chatgpt'
    assert '"status": "unavailable"' in row['planning_request']
    assert engine.missions.list()==[] and engine.tasks.list()==[]


def proposed(review=None):
    return {'text':json.dumps({'plan':MissionPlan.model_validate(dict(title='Review component',
        objective='Test the fixed API negative fences only', deliverables=['Independent verdict'],
        steps=[dict(id='review',title='Review fixed contract',kind='independent_review',
                    acceptance='Seven fixed API negative fences',independent_review=review or descriptor())])).model_dump(),
        'acceptance_step':'review'})}


def test_prompt_gets_exact_registered_contract_native_invention_rejected_manual_review_unchanged(runtime,monkeypatch):
    install_test_seams(monkeypatch)
    engine,backlog,_=runtime
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','catalog-planning','Work:\n- Check API negative fences',
        source_revision='a'*40,planner_mode='chatgpt')
    result=asyncio.run(service.plan_next(state['id'],state['revision']))
    row=result['sections'][0]['items'][0]
    prompt=row['planning_request']
    assert 'b'*64 in prompt and 'api-negative-fences' in prompt
    assert 'negative-fence contract cannot establish generic functional correctness' in prompt
    assert 'combined-source contract' in prompt
    accepted=service._validate_planner_response(proposed(),state,row,False,require_discovered_contract=True)
    assert accepted['planning']=='needs_review'
    altered={**descriptor(),'contract_sha256':'c'*64}
    with pytest.raises(ValueError,match='installed exact'):
        service._validate_planner_response(proposed(altered),state,row,False,require_discovered_contract=True)
    assert service._validate_planner_response(proposed(altered),state,row,False)['planning']=='needs_review'
    assert engine.missions.list()==[] and engine.tasks.list()==[]
    assert 'jules_placement' not in service.get(state['id'])


def test_fixed_path_and_manifest_schema_cannot_be_caller_supplied():
    assert str(catalog.MANIFEST).replace('\\','/')=='/etc/kingdom/independent-test-contracts.json'
    with pytest.raises(TypeError):catalog.discover_contracts('kingdom',base_revision='a'*40,path='/tmp/agent.json')
    with pytest.raises(ValueError):catalog._unique_object([('version',1),('version',1)])


@pytest.mark.parametrize('final_kind',['project_test','independent_review'])
def test_every_native_external_step_must_be_registered_even_before_valid_acceptance(runtime,monkeypatch,final_kind):
    install_test_seams(monkeypatch)
    engine,backlog,_=runtime
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','all-external-steps','Work:\n- Check all stages',source_revision='a'*40)
    row=state['sections'][0]['items'][0]
    data=json.loads(proposed()['text'])
    first=copy.deepcopy(data['plan']['steps'][0]);first['id']='earlier'
    final=(local_test_plan().model_dump()['steps'][0] if final_kind=='project_test'
           else copy.deepcopy(data['plan']['steps'][0]))
    final['depends_on']=['earlier']
    data['plan']['steps']=[first,final];data['acceptance_step']=final['id']
    assert service._validate_planner_response({'text':json.dumps(data)},state,row,False,
        require_discovered_contract=True)['planning']=='needs_review'
    first['independent_review']['contract_sha256']='c'*64
    with pytest.raises(ValueError,match='installed exact'):
        service._validate_planner_response({'text':json.dumps(data)},state,row,False,require_discovered_contract=True)
    assert service._validate_planner_response({'text':json.dumps(data)},state,row,False)['planning']=='needs_review'
    assert engine.missions.list()==[] and engine.tasks.list()==[]


@pytest.mark.skipif(os.name!='posix' or os.geteuid()!=0 or os.environ.get('KINGDOM_CATALOG_ISOLATED_FIXTURE')!='1',
                    reason='Explicit isolated root POSIX fixture only; never install into a production host')
def test_actual_fixed_root_manifest_registry_and_permissions_feed_prompt(runtime):
    # The opt-in test runner supplies an empty private /etc/kingdom tmpfs.
    manifest_path=Path('/etc/kingdom/independent-test-contracts.json')
    registry_path=Path('/etc/kingdom/independent-reviewers.json')
    if manifest_path.exists() or registry_path.exists():
        pytest.skip('Never overwrite existing operator configuration')
    directory=manifest_path.parent
    if not directory.is_dir():pytest.skip('Isolated empty /etc/kingdom fixture mount required')
    try:
        manifest_path.write_text(json.dumps(manifest()));manifest_path.chmod(0o644)
        registry_path.write_text(json.dumps({'version':1,'reviewers':reviewers()}));registry_path.chmod(0o644)
        result=catalog.discover_contracts('kingdom',base_revision='a'*40)
        assert result['status']=='available' and result['contracts'][0]['descriptor']==descriptor()
        engine,backlog,_=runtime
        service=WorkProgrammes(backlog.db,engine,backlog)
        state=service.create('kingdom','real-fixed-manifest','Work:\n- Check fixed fences',source_revision='a'*40,planner_mode='chatgpt')
        planned=asyncio.run(service.plan_next(state['id'],state['revision']))
        assert 'api-negative-fences' in planned['sections'][0]['items'][0]['planning_request']
        assert engine.missions.list()==[] and engine.tasks.list()==[]
        manifest_path.chmod(0o666)
        assert catalog.discover_contracts('kingdom',base_revision='a'*40)['status']=='unavailable'
    finally:
        manifest_path.unlink(missing_ok=True);registry_path.unlink(missing_ok=True)
