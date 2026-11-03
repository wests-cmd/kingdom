"""Owner negative closure from bounded provider observations; never patch acceptance."""
import hashlib
import json
import sqlite3
import urllib.parse
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.integrations.jules_rejection import ProviderTerminalObservation, LOCAL_PHASES, no_uncertain_outbound

FORMAT='kingdom.owner-terminal-session-rejection.v1'
SCOPE='Observed terminal session and bounded artifacts; no immutable finality, test acceptance or remote cancellation claim'

# Assignment binding intentionally has no caller-nominated artifact digest.
class SessionBinding(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    job_id: str=Field(pattern=r'^jules-[a-f0-9]{12}$')
    project: str=Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    backlog_id: str=Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    repository: str=Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    source: str=Field(pattern=r'^sources/github/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    base_revision: str=Field(pattern=r'^[a-f0-9]{40}$')
    branch: str=Field(min_length=1,max_length=150)
    session: str=Field(pattern=r'^sessions/[A-Za-z0-9_-]{1,150}$')

class SessionRejectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expected_job_binding: SessionBinding
    expected_record_version: int=Field(ge=1)
    reason: Literal['outcome_not_implemented','outside_assignment_scope','owner_rejected']

class ObservedArtifact(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    source: str=Field(max_length=250)
    base_revision: str=Field(pattern=r'^[a-fA-F0-9]{40}$')
    patch_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    patch_bytes: int=Field(ge=1,le=2000000)

class SessionRejectionEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    format: Literal['kingdom.owner-terminal-session-rejection.v1']
    binding: SessionBinding
    expected_record_version: int=Field(ge=1)
    reason: Literal['outcome_not_implemented','outside_assignment_scope','owner_rejected']
    operator: Literal['owner']
    before: ProviderTerminalObservation
    after: ProviderTerminalObservation
    artifact_status: Literal['none_observed','observed']
    artifacts: list[ObservedArtifact]=Field(max_length=300)
    activities_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    scope: Literal['Observed terminal session and bounded artifacts; no immutable finality, test acceptance or remote cancellation claim']

class SessionRejectionResponse(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id: str=Field(pattern=r'^jules-[a-f0-9]{12}$')
    phase: Literal['rejected']
    accepted: Literal[False]
    record_version: int=Field(ge=1)
    deadline_at: float=Field(ge=0,allow_inf_nan=False)
    session_rejection: SessionRejectionEvidence

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def binding(job):
    return SessionBinding.model_validate({**{k:job[k] for k in ('project','backlog_id','repository','source','branch','session')},
        'job_id':job['id'],'base_revision':job['revision']}).model_dump()

def current(service,job):
    try:
        evidence=SessionRejectionEvidence.model_validate(job['session_rejection']).model_dump()
        if job['phase']!='rejected' or job.get('accepted') is not False or not no_uncertain_outbound(job):return False
        if evidence['binding']!=binding(job):return False
        for observation in (evidence['before'],evidence['after']):
            if observation['session']!=job['session'] or observation['source']!=job['source']:return False
        if (evidence['artifact_status']=='none_observed')!= (not evidence['artifacts']):return False
        with service.db.get_connection() as conn:
            row=conn.execute('SELECT evidence_json FROM jules_session_rejections WHERE job_id=?',(job['id'],)).fetchone()
            return bool(row and json.loads(row[0])==evidence)
    except (KeyError,TypeError,ValueError):return False
    except sqlite3.Error:return False

def observation_authority(service,job):
    settings=service.settings()
    if (not settings['enabled'] or not settings['has_credentials'] or job['source'] not in settings['allowed_sources']
        or job['repository'] not in settings['allowed_repositories']):raise ValueError('Provider observation authority unavailable')

def observe(service,job,opener):
    observation_authority(service,job)
    reply=service.request(job['session'],opener=opener,timeout=10)
    if (not isinstance(reply,dict) or reply.get('name')!=job['session'] or reply.get('state')!='COMPLETED'
        or not isinstance(reply.get('sourceContext'),dict) or reply['sourceContext'].get('source')!=job['source']):
        raise ValueError('Matching provider COMPLETED observation required')
    return ProviderTerminalObservation.model_validate(dict(session=job['session'],source=job['source'],state='COMPLETED',
        observed_at=service.clock(),response_sha256=digest(reply))).model_dump()

def reject_terminal_session(service,job_id,*,expected_job_binding,expected_record_version,reason,opener=None):
    request=SessionRejectionRequest.model_validate(dict(expected_job_binding=expected_job_binding,
        expected_record_version=expected_record_version,reason=reason)).model_dump()
    job=service.get_job(job_id);expected=request['expected_job_binding']
    if binding(job)!=expected:raise ValueError('Assignment binding changed')
    def identical(saved):
        e=saved.get('session_rejection',{})
        return current(service,saved) and all(e.get(k)==request[k] for k in ('expected_record_version','reason'))
    if job['phase']=='rejected':
        if identical(job):return job
        raise ValueError('Existing negative closure differs')
    def eligible(saved):
        return (saved['phase'] in LOCAL_PHASES and not saved.get('accepted') and no_uncertain_outbound(saved)
            and saved['record_version']==expected_record_version and binding(saved)==expected)
    if not eligible(job):raise ValueError('Assignment changed or uncertain outbound work remains')
    observation_authority(service,job)
    before=observe(service,job,opener)
    page='';seen=set();artifacts=[];page_digests=[]
    for _ in range(12):
        suffix='/activities?pageSize=25'+('&pageToken='+urllib.parse.quote(page,safe='') if page else '')
        data=service.request(job['session']+suffix,opener=opener,timeout=10)
        if not isinstance(data,dict) or not isinstance(data.get('activities'),list) or len(data['activities'])>25:
            raise ValueError('Malformed activity page')
        page_digests.append(digest(data))
        for activity in data['activities']:
            if not isinstance(activity,dict) or not isinstance(activity.get('artifacts',[]),list):raise ValueError('Malformed artifacts')
            for artifact in activity.get('artifacts',[]):
                if not isinstance(artifact,dict) or not isinstance(artifact.get('changeSet',{}),dict):raise ValueError('Malformed artifact')
                if 'changeSet' not in artifact:raise ValueError('Unknown artifact cannot establish no-artifact observation')
                change=artifact['changeSet'];patch=change.get('gitPatch')
                if change.get('source')!=job['source'] or not isinstance(patch,dict):raise ValueError('Artifact source or patch unavailable')
                value=patch.get('unidiffPatch')
                if not isinstance(value,str):raise ValueError('Artifact patch unavailable')
                artifacts.append(ObservedArtifact.model_validate(dict(source=change['source'],base_revision=patch.get('baseCommitId'),
                    patch_sha256=hashlib.sha256(value.encode()).hexdigest(),patch_bytes=len(value.encode()))).model_dump())
                if len(artifacts)>300:raise ValueError('Artifact observation limit')
        page=data.get('nextPageToken','')
        if not isinstance(page,str) or len(page)>2000:raise ValueError('Malformed pagination')
        if not page:break
        if page in seen:raise ValueError('Repeated activity page')
        seen.add(page)
    if page:raise ValueError('Incomplete bounded activity observation')
    after=observe(service,job,opener)
    evidence=SessionRejectionEvidence.model_validate(dict(format=FORMAT,binding=expected,expected_record_version=expected_record_version,
        reason=reason,operator='owner',before=before,after=after,artifact_status='observed' if artifacts else 'none_observed',
        artifacts=artifacts,activities_sha256=digest(page_digests),scope=SCOPE)).model_dump()
    with service.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');saved=service.get_job(job_id)
        if saved['phase']=='rejected' and identical(saved):return saved
        if not eligible(saved):raise ValueError('Assignment changed during provider observation')
        observation_authority(service,saved)
        conn.execute('CREATE TABLE IF NOT EXISTS jules_session_rejections(job_id TEXT PRIMARY KEY,evidence_json TEXT NOT NULL)')
        conn.execute('INSERT INTO jules_session_rejections VALUES(?,?)',(job_id,json.dumps(evidence,sort_keys=True)))
        saved.update(phase='rejected',accepted=False,remote_state='COMPLETED',session_rejection=evidence,
            reason='Owner negative closure of observed terminal session; no acceptance or immutable artifact finality')
        service._save_job(conn,saved);conn.commit()
    if service.engine and hasattr(service.engine,'events'):
        service.engine.events.publish('jules.session_rejected',{'id':job_id,'project':saved['project'],'backlog_id':saved['backlog_id'],'reason':reason})
    return saved
