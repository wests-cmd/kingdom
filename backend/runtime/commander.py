"""Bounded Commander planning: model drafts, owner approves, existing mission verifies."""
import json
import math
import time
from backend.runtime.missions import MissionPlan,validate_plan


def binding(group_id):
    from backend.cluster.hierarchy_api import hierarchy
    from backend.cluster.shared_groups import configured
    if configured().authority():raise ValueError('Shared groups require their authority controller')
    group=next((g for g in hierarchy.groups() if g['id']==group_id),None)
    if not group:raise ValueError('Unknown local group')
    members=[]
    for node in hierarchy.computers():
        if node.node_id not in group['members'] or node.node_state not in {'APPROVED','CONNECTED'} or 'compute' not in node.granted_capabilities:
            continue
        expires=(node.connection_metadata or {}).get('membership_expires_at')
        if expires is not None and (type(expires) not in (int,float) or not math.isfinite(expires) or expires<=time.time()):
            continue
        members.append(node.node_id)
    if not members or group['captain'] not in members:
        raise ValueError('Group needs an approved compute-capable Captain and Knight')
    return {'group_id':group_id,'group_version':hierarchy.group_version(),
            'captain':group['captain'],'members':sorted(members)}


def validate_group_plan(plan,authority):
    validate_plan(plan)
    if not 2<=len(plan.steps)<=8 or plan.offload_analysis:
        raise ValueError('Use 2–8 explicitly assigned analysis steps')
    for step in plan.steps:
        if (step.kind not in {'text_check','python_check'} or step.computer_id not in authority['members']
                or step.input_from or step.argv or step.path or step.repair_source or len(step.instructions)>16000):
            raise ValueError('Commander only drafts bounded literal analyses within its current group')
    return plan


async def draft(objective,profile,group_id,models,missions):
    authority=binding(group_id)
    prompt=('Draft a MissionPlan JSON with 2–8 bounded literal analysis steps for the objective. '
            'Every step must be text_check or python_check and have one computer_id from the supplied member list. '
            'No commands, files, tool grants, generated bindings or unreviewed side effects. '
            'Use dependencies for ordered work. Return only JSON, and list unresolved requirements rather than inventing a completed action.\n'
            'Allowed members: '+json.dumps(authority['members'])+'\nSchema: '+json.dumps(MissionPlan.model_json_schema())+
            '\nUser objective: '+objective)
    result=await models.chat(profile,{'messages':[{'role':'user','content':prompt}],'stream':False})
    choice=result['choices'][0]
    if choice.get('finish_reason')=='length':raise ValueError('Incomplete Commander draft')
    plan=MissionPlan.model_validate_json(choice['message']['content'])
    # The objective is the owner's input, never a model rewrite of authority.
    plan.objective=objective
    validate_group_plan(plan,authority)
    if binding(group_id)!=authority:raise ValueError('Group authority changed during planning')
    return missions.create(plan,model_profile=profile,group_binding=authority)
