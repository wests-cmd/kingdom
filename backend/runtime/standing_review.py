"""Owner-scoped review of data-only function missions; never new capabilities."""
import hashlib
import json
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field


class StandingReviewError(ValueError):
    """Only fixed review diagnostics, never provider bodies or model text."""


class FunctionReviewScope(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled: bool = False
    write_prefix: str = Field(min_length=10,max_length=200)
    read_sources: dict[str,str] = Field(default_factory=dict,max_length=12)
    max_missions: int = Field(default=1,ge=1,le=12)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def profile_digest(profile):
    return digest({k:v for k,v in profile.items() if k not in {'api_key','updated_at','has_credentials'}})


def relative_path(value):
    if not isinstance(value,str) or '\\' in value or ':' in value or any(ord(c)<32 for c in value):
        raise StandingReviewError('Use a relative project path')
    path=PurePosixPath(value)
    if path.is_absolute() or len(path.parts)<2 or path.parts[0]!='projects' or any(p in {'.','..'} for p in value.split('/')):
        raise StandingReviewError('Use a bounded project path')
    return str(path)


def validate_scope(value):
    scope=FunctionReviewScope.model_validate(value).model_dump()
    scope['write_prefix']=relative_path(scope['write_prefix'])
    for path,sha in scope['read_sources'].items():
        if relative_path(path)!=path or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Read sources need exact paths and SHA256 digests')
    return scope


def review_function_plan(programme,row,profile):
    from backend.models.planner_routing import hosting
    from backend.runtime.bounded_function_tests import PROFILE,profile_hash
    from backend.runtime.computer_tools import workspace_path
    from backend.runtime.missions import MissionPlan,validate_plan
    if row.get('consultation_id'):
        raise StandingReviewError('Retained help requires explicit review; prior local stages do not attest this proposal')
    saved=programme.get('standing_review',{})
    scope=validate_scope(saved['scope'])
    if not scope['enabled'] or programme.get('planner_mode')!='deliberative' or programme.get('planner_routing')!='local':
        raise StandingReviewError('Standing review requires enabled local deliberation')
    if hosting(profile)!='local' or profile.get('disabled') or profile_digest(profile)!=saved['profile_sha256']:
        raise StandingReviewError('Approved local model configuration changed')
    for stage in ['plan_a','plan_b','critique','synthesis']:
        evidence=row.get('planning_stages',{}).get(stage,{})
        if evidence.get('hosting')!='local' or evidence.get('profile')!=programme['model_profile'] or not evidence.get('text'):
            raise StandingReviewError('Required local deliberation evidence is missing')
    if 'synthesis_repair' in row.get('planning_stages',{}):
        evidence=row['planning_stages']['synthesis_repair']
        if evidence.get('hosting')!='local' or evidence.get('profile')!=programme['model_profile']:
            raise StandingReviewError('Repair used a different planning connection')
    plan=validate_plan(MissionPlan.model_validate(row['proposal']))
    if plan.missing_requirements or plan.offload_analysis or not 3<=len(plan.steps)<=6:
        raise StandingReviewError('Plan exceeds the bounded function scope')
    checks=[s for s in plan.steps if s.kind=='function_check']
    writes=[s for s in plan.steps if s.kind=='write_file']
    if len(checks)!=1 or len(writes)!=1 or checks[0].id!=row['acceptance_step'] or plan.steps[-1].id!=checks[0].id:
        raise StandingReviewError('One final immutable function check is required')
    if checks[0].case_profile!=PROFILE or checks[0].case_profile_sha256!=profile_hash(PROFILE):
        raise StandingReviewError('Immutable tests changed')
    prefix=scope['write_prefix']+'/'
    for step in plan.steps:
        if step.kind not in {'model','write_file','read_file','function_check'} or step.argv or step.computer_id or step.build or step.project_test:
            raise StandingReviewError('Plan requests an operation outside standing scope')
        if step.kind in {'read_file','write_file'}:
            path=relative_path(step.path)
            target=workspace_path(path)
            # Reject aliases, including symlinks into another workspace project.
            if target != workspace_path()/path:
                raise StandingReviewError('Project path resolves through an alias')
            if step.kind=='write_file' and not path.startswith(prefix):
                raise StandingReviewError('Write is outside the owner project prefix')
            if step.kind=='read_file' and not path.startswith(prefix):
                expected=scope['read_sources'].get(path)
                if not expected or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
                    raise StandingReviewError('Read source lacks its owner-approved digest')
    return {'kind':'owner-scoped-function-policy-v1','scope_version':saved['version'],
            'proposal_sha256':digest(plan.model_dump()),'profile_sha256':saved['profile_sha256']}


def dispatch_allowed(engine,programme,row,mission):
    """Revocation takes effect before further mission dispatch; old receipts remain facts."""
    from backend.models.profiles import ModelProfiles
    basis=row.get('review_basis')
    if not basis:return True
    try:
        if basis['kind']!='owner-scoped-function-policy-v1' or engine.execution_policy.get()['level']!=5:
            return False
        current=review_function_plan(programme,row,ModelProfiles(engine.missions.db).get(programme['model_profile']))
        return current==basis and digest(mission['plan'])==basis['proposal_sha256']
    except (ValueError,KeyError,TypeError,OSError):return False


def task_allowed(engine,task):
    """Recheck queued work against current consent at execution authorization."""
    ident=task.get('metadata',{}).get('mission_id')
    if not ident:return True
    with engine.missions.db.get_connection() as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_programmes'").fetchone():return True
        records=connection.execute('SELECT state_json FROM work_programmes').fetchall()
    for record in records:
        programme=json.loads(record[0])
        for section in programme['sections']:
            for row in [*section['items'],section['integration']]:
                if row.get('mission_id')!=ident or not row.get('review_basis'):continue
                mission=engine.missions.get(ident)
                known={s['task_id'] for s in mission.get('steps',{}).values() if s.get('task_id')}
                if mission.get('repair',{}):known.add(mission['repair'].get('task_id'))
                return task['id'] in known and dispatch_allowed(engine,programme,row,mission)
    return True
