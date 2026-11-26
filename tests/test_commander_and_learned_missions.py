from types import SimpleNamespace
from uuid import uuid5,NAMESPACE_URL
import pytest
from backend.runtime.missions import MissionPlan
from backend.runtime.commander import validate_group_plan
from backend.runtime.learned_missions import candidate
from backend.runtime.harness_protocol import decode,proposal_plan
import json


def sample():
    return MissionPlan(title='Two analyses',objective='Review inputs',deliverables=['Checks'],steps=[
        {'id':'a','title':'First','kind':'text_check','instructions':'hello','acceptance':'Measured text'},
        {'id':'b','title':'Second','kind':'python_check','instructions':'x=1','acceptance':'Parsed code','depends_on':['a']} ])


def test_commander_refuses_out_of_group_and_action_steps():
    plan=sample()
    for step in plan.steps:step.computer_id='a'
    authority={'members':['a']}
    assert validate_group_plan(plan,authority)==plan
    plan.steps[1].computer_id='b'
    with pytest.raises(ValueError):validate_group_plan(plan,authority)
    plan.steps[1].computer_id='a';plan.steps[1].kind='command';plan.steps[1].argv=['echo','x']
    with pytest.raises(ValueError):validate_group_plan(plan,authority)


def test_learned_mission_revalidates_exact_controller_receipts():
    plan=sample().model_dump()
    state={'id':'mission','version':1,'approved_version':1,'status':'completed','plan':plan,'steps':{}}
    rows={}
    for step in plan['steps']:
        key='mission:1:'+step['id']
        task_id=str(uuid5(NAMESPACE_URL,'kingdom-mission:'+key))
        state['steps'][step['id']]={'status':'verified','task_id':task_id}
        rows[task_id]={'status':'completed','prompt':step['instructions'],
            'metadata':{'_mission_step_key':key,'mission_id':'mission','mission_version':1,'step_id':step['id'],
                'tool':'text.analyze@1.0.0' if step['kind']=='text_check' else 'code.python.analyze@1.0.0',
                'tool_parameters':{'text':step['instructions']}},
            'result':{'results':[{'verification':{'state':'VERIFIED'},'outcome':{'output':{'ok':True}}}]}}
    repository=SimpleNamespace(get=rows.get)
    learned=candidate(state,repository)
    assert learned['status']=='review_required' and len(learned['task_ids'])==2
    rows[learned['task_ids'][0]]['result']['results'][0]['verification']['state']='UNVERIFIED'
    assert candidate(state,repository) is None


def test_harness_protocol_only_creates_reviewable_literal_analysis_plan():
    raw='\n'.join(json.dumps(item) for item in [
        {'type':'progress','message':'Working'},
        {'type':'proposal','tool':'text.analyze@1.0.0','text':'literal'},
        {'type':'answer','text':'Please review'}])
    parsed=decode(raw)
    assert parsed['answer']=='Please review'
    plan=proposal_plan(parsed['proposals'])
    assert plan.steps[0].kind=='text_check' and plan.steps[0].argv==[]
    with pytest.raises(ValueError):decode(raw+'\n'+json.dumps({'type':'proposal','tool':'process.run@1.0.0','text':'echo'}))
