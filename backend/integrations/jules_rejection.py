"""Owner rejection of an exact returned candidate, never independent test acceptance."""
import hashlib
import json
import math
import sqlite3
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

FORMAT='kingdom.owner-candidate-rejection.v1'
REASONS={'outcome_not_implemented','outside_assignment_scope','owner_rejected'}
LOCAL_PHASES={'awaiting_independent_review','review_required','expired_remote_may_continue','cancelled'}

class CandidateBinding(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    job_id: str=Field(pattern=r'^jules-[a-f0-9]{12}$')
    project: str=Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    backlog_id: str=Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    repository: str=Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    source: str=Field(pattern=r'^sources/github/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    base_revision: str=Field(pattern=r'^[a-f0-9]{40}$')
    branch: str=Field(min_length=1,max_length=150)
    session: str=Field(pattern=r'^sessions/[A-Za-z0-9_-]{1,150}$')
    patch_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')

class RejectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expected_job_binding: CandidateBinding
    expected_record_version: int=Field(ge=1)
    reason: Literal['outcome_not_implemented','outside_assignment_scope','owner_rejected']

class ProviderTerminalObservation(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    session: str=Field(pattern=r'^sessions/[A-Za-z0-9_-]{1,150}$')
    source: str=Field(pattern=r'^sources/github/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    state: Literal['COMPLETED']
    observed_at: float=Field(ge=0,allow_inf_nan=False)
    response_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')

class CandidateRejectionEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    format: Literal['kingdom.owner-candidate-rejection.v1']
    binding: CandidateBinding
    expected_record_version: int=Field(ge=1)
    reason: Literal['outcome_not_implemented','outside_assignment_scope','owner_rejected']
    operator: Literal['owner']
    provider_observation: ProviderTerminalObservation
    scope: Literal['Owner rejected the candidate; no test acceptance or remote cancellation claim']

class RejectionResponse(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id: str=Field(pattern=r'^jules-[a-f0-9]{12}$')
    phase: Literal['rejected']
    accepted: Literal[False]
    record_version: int=Field(ge=1)
    deadline_at: float=Field(ge=0,allow_inf_nan=False)
    rejection: CandidateRejectionEvidence


def binding(job):
    candidate=job.get('candidate') or {}
    return CandidateBinding.model_validate(dict(job_id=job['id'],project=job['project'],backlog_id=job['backlog_id'],
        repository=job['repository'],source=job['source'],base_revision=job['revision'],branch=job['branch'],
        session=job.get('session'),patch_sha256=candidate.get('patch_sha256'))).model_dump()

def _patch(conn,job):
    row=conn.execute('SELECT patch FROM jules_candidate_patches WHERE job_id=?',(job['id'],)).fetchone()
    if not row or hashlib.sha256(row[0].encode()).hexdigest()!=job.get('candidate',{}).get('patch_sha256'):
        raise ValueError('Exact retained provider patch is unavailable or changed')
    if job['candidate'].get('base_revision')!=job['revision']:
        raise ValueError('Retained provider base differs from the assignment')

def no_uncertain_outbound(job):
    return (not any(row.get('status') in {'sending','unknown'} for row in job.get('repair_history',[]))
            and not any(row.get('outcome') in {'claimed_outcome_unconfirmed','unknown'} for row in job.get('scope_reminders',[])))

def terminal_rejection_current(service,job):
    """Only the atomically retained bound owner rejection releases an admission slot."""
    try:
        if job['phase']!='rejected' or job.get('accepted') is not False or not no_uncertain_outbound(job):return False
        rejection=job.get('rejection') or {}
        observed=rejection.get('provider_observation') or {}
        expected=binding(job)
        if (rejection.get('format')!=FORMAT or rejection.get('binding')!=expected or rejection.get('reason') not in REASONS
                or observed.get('state')!='COMPLETED' or observed.get('session')!=expected['session']
                or observed.get('source')!=expected['source']):return False
        with service.db.get_connection() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jules_candidate_rejections'").fetchone():return False
            row=conn.execute('SELECT rejection_json FROM jules_candidate_rejections WHERE job_id=?',(job['id'],)).fetchone()
            _patch(conn,job)
            return bool(row and json.loads(row[0])==rejection)
    except (KeyError,TypeError,ValueError,sqlite3.Error):return False

def reject_candidate(service,job_id,*,expected_job_binding,expected_record_version,reason,opener=None):
    request=RejectionRequest.model_validate(dict(expected_job_binding=expected_job_binding,
        expected_record_version=expected_record_version,reason=reason)).model_dump()
    job=service.get_job(job_id)
    expected=request['expected_job_binding']
    if job['id']!=expected['job_id'] or binding(job)!=expected:
        raise ValueError('Expected candidate belongs to different work')
    if job['phase']=='rejected':
        rejection=job.get('rejection') or {}
        if (terminal_rejection_current(service,job) and rejection.get('expected_record_version')==expected_record_version
                and rejection.get('reason')==reason):return job
        raise ValueError('Existing rejection differs from this request')
    if (job['phase'] not in LOCAL_PHASES or job.get('accepted') or not no_uncertain_outbound(job)
            or job['record_version']!=expected_record_version):
        raise ValueError('Candidate phase or record version changed; reload')
    with service.db.get_connection() as conn:_patch(conn,job)
    settings=service.settings()
    if (not settings['enabled'] or not settings['has_credentials'] or job['source'] not in settings['allowed_sources']
            or job['repository'] not in settings['allowed_repositories']):
        raise ValueError('Existing provider observation scope is disabled or revoked')
    # Explicit owner-requested read only. Old execution/review deadlines are not renewed.
    reply=service.request(job['session'],opener=opener,timeout=10)
    if (not isinstance(reply,dict) or reply.get('name')!=job['session'] or reply.get('state')!='COMPLETED'
            or not isinstance(reply.get('sourceContext'),dict) or reply['sourceContext'].get('source')!=job['source']):
        raise ValueError('Bound provider session has not independently reported COMPLETED')
    now=service.clock()
    if type(now) not in (int,float) or not math.isfinite(now):raise ValueError('Finite observation time required')
    observation=dict(session=job['session'],source=job['source'],state='COMPLETED',observed_at=now,
        response_sha256=hashlib.sha256(json.dumps(reply,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest())
    rejection=dict(format=FORMAT,binding=expected,expected_record_version=expected_record_version,reason=reason,
        operator='owner',provider_observation=observation,scope='Owner rejected the candidate; no test acceptance or remote cancellation claim')
    with service.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current=service.get_job(job_id)
        if current['phase']=='rejected':
            if (terminal_rejection_current(service,current) and current.get('rejection')==rejection):return current
            # Concurrent identical requests may observe different GET timestamps: compare immutable request.
            saved=current.get('rejection') or {}
            if (terminal_rejection_current(service,current) and saved.get('binding')==expected
                    and saved.get('expected_record_version')==expected_record_version and saved.get('reason')==reason):return current
            raise ValueError('Concurrent rejection differs from this request')
        if (current['record_version']!=expected_record_version or current['phase'] not in LOCAL_PHASES
                or current.get('accepted') or not no_uncertain_outbound(current) or binding(current)!=expected):
            raise ValueError('Candidate changed while observing provider; no rejection committed')
        _patch(conn,current)
        conn.execute('CREATE TABLE IF NOT EXISTS jules_candidate_rejections(job_id TEXT PRIMARY KEY,rejection_json TEXT NOT NULL)')
        conn.execute('INSERT INTO jules_candidate_rejections VALUES(?,?)',(job_id,json.dumps(rejection,sort_keys=True)))
        current.update(phase='rejected',accepted=False,remote_state='COMPLETED',rejection=rejection,
            reason='Owner rejected exact candidate after bound provider terminal observation; no acceptance or release')
        service._save_job(conn,current);conn.commit()
    if service.engine and hasattr(service.engine,'events'):
        service.engine.events.publish('jules.candidate_rejected',{'id':job_id,'project':current['project'],
            'backlog_id':current['backlog_id'],'patch_sha256':expected['patch_sha256'],'reason':reason})
    return current
