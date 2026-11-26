"""Evidence-backed reusable mission candidates. Replay always creates a new draft."""
from copy import deepcopy
from uuid import uuid5,NAMESPACE_URL
from backend.runtime.missions import MissionPlan,validate_plan


def candidate(state,task_repository):
    if state.get('status')!='completed' or state.get('approved_version')!=state.get('version'):
        return None
    plan=state['plan']
    if not 2<=len(plan.get('steps',[]))<=12 or state.get('attachment_ids') or plan.get('missing_requirements'):
        return None
    retained=[]
    for step in plan['steps']:
        # Only bounded literal pure analyses. No generated bindings, commands,
        # private file reads, pinned computer, or imported approvals.
        if (step['kind'] not in {'text_check','python_check'} or step.get('input_from')
                or step.get('computer_id') or step.get('argv') or step.get('path')
                or len(step.get('instructions',''))>16000):
            return None
        record=state.get('steps',{}).get(step['id'],{})
        key=f"{state['id']}:{state['version']}:{step['id']}"
        task_id=str(uuid5(NAMESPACE_URL,'kingdom-mission:'+key))
        if record.get('status')!='verified' or record.get('task_id')!=task_id:
            return None
        task=task_repository.get(task_id)
        if not task or task.get('status','').lower()!='completed':
            return None
        meta=task.get('metadata',{})
        tool='text.analyze@1.0.0' if step['kind']=='text_check' else 'code.python.analyze@1.0.0'
        if (meta.get('_mission_step_key')!=key or meta.get('mission_id')!=state['id']
                or meta.get('mission_version')!=state['version'] or meta.get('step_id')!=step['id']
                or meta.get('tool')!=tool or meta.get('tool_parameters')!={'text':step['instructions']}
                or task.get('prompt')!=(step['instructions'] or step['title'])):
            return None
        from backend.runtime.missions import MissionService
        try:MissionService.verified_outputs(task)
        except (ValueError,TypeError,AttributeError):return None
        retained.append(task_id)
    replay=deepcopy(plan)
    replay['offload_analysis']=False
    validate_plan(MissionPlan.model_validate(replay))
    return {'source_mission_id':state['id'],'source_version':state['version'],
            'task_ids':retained,'plan':replay,'status':'review_required',
            'scope':'Literal independently verified analyses only; new approval required'}
