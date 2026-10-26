"""Verify a protected independent runner's exact-patch test attestation.

The runner holds the private key outside the execution agent. The application
only reads a root-owned trust registry. Caller flags and source labels never
substitute for this signature. Installing a reviewer is an operator operation,
not an agent tool or model-generated policy.
"""
import base64
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REGISTRY = Path('/etc/kingdom/independent-reviewers.json')
CONTEXT = b'kingdom.independent-patch-test.v2\0'
BINDING = {'job_id','project','backlog_id','mission_id','mission_version','step_id',
           'source','base_revision','patch_sha256','contract_sha256'}


def canonical(payload):
    return CONTEXT + json.dumps(payload,sort_keys=True,separators=(',',':'),
                                ensure_ascii=True,allow_nan=False).encode()


def reviewer_registry():
    """Fail closed unless the OS protects the fixed registry from the agent."""
    if os.name != 'posix':
        raise ValueError('Protected reviewer registry is not configured on this platform')
    try:
        if REGISTRY.resolve() != REGISTRY.absolute():
            raise ValueError('Reviewer registry must not use symlinks')
        for path in [REGISTRY,*REGISTRY.parents]:
            value=path.stat()
            if value.st_uid != 0 or value.st_mode & 0o022:
                raise ValueError('Reviewer registry must be root-owned and not group/world writable')
        if not stat.S_ISREG(REGISTRY.stat().st_mode) or REGISTRY.stat().st_size>65536:
            raise ValueError('Invalid reviewer registry')
        data=json.loads(REGISTRY.read_text())
        if data.get('version')!=1 or not isinstance(data.get('reviewers'),dict):
            raise ValueError('Invalid reviewer registry format')
        return data['reviewers']
    except (OSError,ValueError,TypeError) as error:
        raise ValueError('Independent reviewer trust is unavailable') from error


def verify_attestation(envelope, expected, reviewers, now=None, *, outcome='passed'):
    """Pure signature/binding check; consumption must be atomic with job acceptance."""
    now=time.time() if now is None else now
    try:
        if outcome not in {'passed','failed'}:raise ValueError('Choose a fixed independent verdict outcome')
        if not isinstance(envelope,dict) or set(envelope)!={'payload','signature'}:
            raise ValueError('Signed independent test attestation required')
        payload=envelope['payload']
        if not isinstance(payload,dict) or set(payload)!={'format','receipt_id','reviewer_id','issued_at','expires_at','binding','execution'}:
            raise ValueError('Invalid attestation fields')
        if payload['format']!='kingdom.patch-test.v2':raise ValueError('Wrong attestation protocol')
        if set(expected)!=BINDING or set(payload['binding'])!=BINDING:
            raise ValueError('Complete exact job binding required')
        for name in BINDING:
            if type(payload['binding'][name]) is not type(expected[name]) or payload['binding'][name]!=expected[name]:
                raise ValueError('Independent test belongs to different work')
        binding=payload['binding']
        if type(binding['mission_version']) is not int or binding['mission_version']<1:
            raise ValueError('Invalid mission version')
        if not re.fullmatch('[a-f0-9]{40}',binding['base_revision']) or any(not isinstance(binding[name],str) or not re.fullmatch('[a-f0-9]{64}',binding[name]) for name in ['patch_sha256','contract_sha256']):
            raise ValueError('Exact source and patch hashes required')
        for name in ['receipt_id','reviewer_id']:
            if not isinstance(payload[name],str) or not re.fullmatch('[A-Za-z0-9_.-]{1,120}',payload[name]):raise ValueError('Invalid receipt identity')
        issued,expiry=payload['issued_at'],payload['expires_at']
        if any(type(v) not in {int,float} or not math.isfinite(v) for v in [issued,expiry]):raise ValueError('Invalid receipt time')
        if issued>now+5 or not issued<expiry or expiry<=now or expiry-issued>3600:
            raise ValueError('Independent test attestation expired or outside its bounded window')
        reviewer=reviewers.get(payload['reviewer_id'])
        if not isinstance(reviewer,dict) or reviewer.get('enabled') is not True or binding['project'] not in reviewer.get('projects',[]) or binding['source'] not in reviewer.get('sources',[]) or binding['contract_sha256'] not in reviewer.get('contracts',[]):
            raise ValueError('Reviewer is unavailable, revoked or out of scope')
        execution=payload['execution']
        required={'run_id','image_sha256','source_archive_sha256','candidate_tree_sha256','argv','test_count','failed_count','exit_code','network_isolated','read_only_source','verdict_origin'}
        if not isinstance(execution,dict) or set(execution)!=required:raise ValueError('Complete independent execution evidence required')
        for field in ['image_sha256','source_archive_sha256','candidate_tree_sha256']:
            if not isinstance(execution[field],str) or not re.fullmatch('[a-f0-9]{64}',execution[field]):raise ValueError('Pinned execution inputs required')
        if not isinstance(execution['run_id'],str) or not 1<=len(execution['run_id'])<=120:raise ValueError('Independent run identity required')
        if not isinstance(execution['argv'],list) or not execution['argv'] or len(execution['argv'])>100 or any(not isinstance(v,str) or not v or len(v)>1000 for v in execution['argv']):raise ValueError('Exact independent test command required')
        if outcome=='passed':
            if type(execution['test_count']) is not int or execution['test_count']<1 or type(execution['failed_count']) is not int or execution['failed_count']!=0 or type(execution['exit_code']) is not int or execution['exit_code']!=0:
                raise ValueError('Nonempty passing independent suite required')
        elif (type(execution['test_count']) is not int or execution['test_count']<0
              or type(execution['failed_count']) is not int or not 0<=execution['failed_count']<=execution['test_count']
              or type(execution['exit_code']) is not int or not -2147483648<=execution['exit_code']<=4294967295
              or (execution['failed_count']==0 and execution['exit_code']==0)):
            raise ValueError('A genuine signed nonpassing execution verdict is required')
        if execution['network_isolated'] is not True or execution['read_only_source'] is not True or execution['verdict_origin']!='external_controller':
            raise ValueError('Independent isolated read-only test execution required')
        key=base64.b64decode(reviewer['public_key'],validate=True)
        signature=base64.b64decode(envelope['signature'],validate=True)
        Ed25519PublicKey.from_public_bytes(key).verify(signature,canonical(payload))
        return payload
    except (KeyError,TypeError,ValueError,InvalidSignature,OverflowError) as error:
        raise ValueError('No current source-bound independent patch acceptance') from error


def delegated_acceptance(database, backlog, now=None):
    """None means no delegated job; False means retained but not yet accepted."""
    with database.get_connection() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jules_jobs'").fetchone():
            return None
        rows=conn.execute('SELECT state_json FROM jules_jobs WHERE project=? AND backlog_id=?',
                          (backlog['project'],backlog['id'])).fetchall()
        if not rows:return None
        if len(rows)!=1:raise ValueError('Ambiguous delegated job binding')
        job=json.loads(rows[0][0])
        if job.get('accepted') is not True or job.get('phase')!='completed':return False
        expected=expected_binding(job,backlog)
        proof=verify_attestation(job.get('attestation'),expected,reviewer_registry(),now=job.get('accepted_at',now))
        retained=conn.execute('SELECT job_id,payload_json FROM jules_accepted_receipts WHERE receipt_id=?',
                              (proof['receipt_id'],)).fetchone()
        if not retained or retained[0]!=job['id'] or json.loads(retained[1])!=proof:
            raise ValueError('Independent receipt was not atomically consumed by this job')
        return proof


def expected_binding(job,backlog):
    intent=backlog['intent'];candidate=job.get('candidate') or {}
    review=job.get('review_contract') or {}
    return dict(job_id=job['id'],project=backlog['project'],backlog_id=backlog['id'],
        mission_id=intent['mission_id'],mission_version=intent['mission_version'],step_id=intent['acceptance_step'],
        source=job['source'],base_revision=job['revision'],patch_sha256=candidate.get('patch_sha256'),contract_sha256=review.get('contract_sha256'))


def current_review_contract(engine,job,backlog):
    from backend.runtime.missions import MissionPlan,validate_plan
    intent=backlog['intent'];mission=engine.missions.get(intent['mission_id'])
    if (mission['version']!=intent['mission_version'] or mission['approved_version']!=intent['mission_version']
            or mission['status'] not in {'approved','running','completed'}):raise ValueError('Current reviewed mission required')
    validate_plan(MissionPlan.model_validate(mission['plan']))
    step=next(step for step in mission['plan']['steps'] if step['id']==intent['acceptance_step'])
    if step['kind']!='independent_review':raise ValueError('A governed external review contract is required; native command summaries are not equivalent')
    review=step['independent_review']
    if review['project']!=job['project'] or review['source']!=job['source'] or review['base_revision']!=job['revision']:
        raise ValueError('Reviewed project/source differs from provider assignment')
    if any(mission['steps'].get(key,{}).get('status') not in {'verified','completed'} for key in step['depends_on']):
        raise ValueError('Review prerequisites have not completed')
    return review


def external_step_acceptance(engine,mission_id,version,step_id):
    database=engine.missions.db
    with database.get_connection() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jules_jobs'").fetchone():return None
        rows=conn.execute('SELECT state_json FROM jules_jobs').fetchall()
        for row in rows:
            job=json.loads(row[0]);work=conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND id=?',(job['project'],job['backlog_id'])).fetchone()
            if not work:continue
            backlog=json.loads(work[0]);intent=backlog['intent']
            if (intent.get('mission_id'),intent.get('mission_version'),intent.get('acceptance_step'))!=(mission_id,version,step_id):continue
            if job.get('accepted') is not True:return None
            review=current_review_contract(engine,job,backlog)
            if review!=job.get('review_contract'):raise ValueError('Accepted external contract changed')
            return delegated_acceptance(database,backlog)
    return None
