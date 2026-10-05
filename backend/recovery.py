"""Explicit owner-approved operational recovery. No source or policy self-modification."""
import time
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from backend.security.http_auth import require_owner
from backend.storage.integration_repository import IntegrationRepository
from backend.events.event_bus import event_bus

router=APIRouter(dependencies=[Depends(require_owner)])
repository=IntegrationRepository()

class PlanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['restart_runtime']

class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    approved: Literal[True]

class RepairPlan(BaseModel):
    plan_id: str
    action: Literal['restart_runtime']
    state: Literal['pending','running','verified','failed','expired']
    summary: str
    effect: str
    before_running: bool
    expires_at: float
    after_running: bool | None = None
    error: str | None = None

class RecoveryStatus(BaseModel):
    ready: bool
    runtime_running: bool
    repairs: list[RepairPlan]
    notice: str

def services():
    from backend.api import engine, health_readiness
    return engine,health_readiness

@router.get('/recovery/status',response_model=RecoveryStatus)
def status():
    engine,health=services()
    try: ready=health()['status']=='ready'
    except HTTPException: ready=False
    plans=[RepairPlan.model_validate(item) for item in repository.list('operational_repair')[-20:][::-1]]
    for plan in plans:
        if plan.state=='pending' and plan.expires_at<=time.time(): plan.state='expired'
    return {'ready':ready,'runtime_running':engine.scheduler.running,
            'repairs':plans,
            'notice':'Only an explicitly approved runtime restart is supported. Source-code repair, policy repair and automatic desktop updates are not enabled.'}

@router.post('/recovery/plans',response_model=RepairPlan)
def create_plan(request:PlanRequest):
    engine,_=services()
    plan=RepairPlan(plan_id=uuid.uuid4().hex,action=request.action,state='pending',
                    summary='Restart Kingdom task processing',
                    effect='Stops and starts the runtime queue. Eligible pending tasks may resume. Application code, access permissions and accessibility settings are not changed.',
                    before_running=engine.scheduler.running,expires_at=time.time()+300)
    repository.put('operational_repair',plan.plan_id,plan.model_dump())
    event_bus.publish('repair.plan_created',{'plan_id':plan.plan_id,'action':plan.action,'actor':'owner'})
    return plan

def claim_plan(plan_id):
    # Serialize competing approvals before any side effect; replay is rejected.
    with repository.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute("SELECT value_json FROM integration_records WHERE kind='operational_repair' AND id=?",(plan_id,)).fetchone()
        if not row: raise HTTPException(404,'Repair plan not found')
        plan=RepairPlan.model_validate_json(row['value_json'])
        if plan.state!='pending': raise HTTPException(409,'Repair plan has already been used')
        if plan.expires_at<=time.time(): raise HTTPException(409,'Repair approval expired; no action was taken')
        running=conn.execute("SELECT id FROM integration_records WHERE kind='operational_repair' AND json_extract(value_json,'$.state')='running' LIMIT 1").fetchone()
        if running: raise HTTPException(409,'Another repair is running or awaiting investigation')
        plan.state='running'
        conn.execute("UPDATE integration_records SET value_json=?,updated_at=? WHERE kind='operational_repair' AND id=?",(plan.model_dump_json(),time.time(),plan_id))
    return plan

@router.post('/recovery/plans/{plan_id}/execute',response_model=RepairPlan)
async def execute_plan(plan_id:str,approval:Approval):
    plan=claim_plan(plan_id)
    engine,_=services()
    event_bus.publish('repair.approved',{'plan_id':plan_id,'actor':'owner'})
    try:
        await engine.stop()
        await engine.start()
        plan.after_running=engine.scheduler.running
        if not plan.after_running: raise RuntimeError('Runtime did not start')
        plan.state='verified'
    except Exception:
        plan.state='failed'
        plan.error='Runtime restart could not be verified. Inspect runtime status before retrying.'
        plan.after_running=engine.scheduler.running
    repository.put('operational_repair',plan_id,plan.model_dump())
    event_bus.publish('repair.finished',{'plan_id':plan_id,'state':plan.state,'actor':'owner'})
    return plan
