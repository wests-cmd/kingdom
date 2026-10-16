from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from backend.security.http_auth import require_owner
from backend.storage.db import db
from backend.api import engine
from backend.runtime.automation import AutomationSupervisor
from backend.runtime.workshop_adapter import WorkshopAdapter
from backend.runtime.durable_automation import DurableAutomations
import os
import sqlite3
from pathlib import Path

router = APIRouter(prefix='/automations', dependencies=[Depends(require_owner)])
state_path = Path(os.environ.get('KINGDOM_AUTOMATION_STATE', 'data/automation/state.sqlite3'))
state_path.parent.mkdir(parents=True, exist_ok=True)
supervisor = AutomationSupervisor(lambda: sqlite3.connect(state_path, timeout=15),
    lambda: engine.execution_policy.get()['level'], engine.events.publish)
if os.environ.get('KINGDOM_WORKSHOP_ROOT'):
    supervisor.register(WorkshopAdapter(os.environ['KINGDOM_WORKSHOP_ROOT']))
scheduled = DurableAutomations(db, engine.events.publish)


class ScheduleRequest(BaseModel):
    project: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    body: str = Field(min_length=1, max_length=8000)
    interval_sec: int = Field(ge=60, le=2592000)
    start_at: float | None = Field(default=None, ge=0)


class ScheduleStatusRequest(BaseModel):
    status: str = Field(pattern=r'^(active|paused|cancelled)$')
    expected_revision: int = Field(ge=1)


class WorkScheduleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    project: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    prompt: str = Field(min_length=1, max_length=20000)
    interval_sec: int = Field(ge=60, le=2592000)
    model_profile: str = Field(default='auto', min_length=1, max_length=100)
    mode: str = Field(default='agent', pattern=r'^(auto|quick|agent)$')
    session_scope: str | None = Field(default=None, max_length=100)
    allow_process: bool = False
    enabled: bool = False
    start_at: float | None = Field(default=None, ge=0)
    review_instructions: str = Field(default='Review execution evidence and tests before continuing.', max_length=2000)


def schedule_boundary(operation):
    try:
        return operation()
    except KeyError as error:
        raise HTTPException(404, 'Schedule not found in this project') from error
    except ValueError as error:
        raise HTTPException(409, 'Invalid schedule or changed revision; reload first') from error


@router.post('/schedules')
def create_schedule(request: ScheduleRequest):
    return schedule_boundary(lambda: scheduled.create(request.project, request.body, request.interval_sec, request.start_at))


@router.post('/schedules/work')
def create_work_schedule(request: WorkScheduleRequest):
    return schedule_boundary(lambda: scheduled.create_work(**request.model_dump()))


@router.get('/schedules/{project}')
def list_schedules(project: str):
    return schedule_boundary(lambda: {'schedules': scheduled.list(project), 'supported_operations': ['record_note', 'enqueue_request'],
        'notice': 'Work creates an idempotent queued request, never runs it automatically. New work schedules start paused unless explicitly enabled.'})


@router.post('/schedules/{project}/{ident}/status')
def schedule_status(project: str, ident: str, request: ScheduleStatusRequest):
    return schedule_boundary(lambda: scheduled.change_status(project, ident, request.status, request.expected_revision))


@router.get('/schedules/{project}/{ident}/receipts')
def schedule_receipts(project: str, ident: str):
    return schedule_boundary(lambda: {'receipts': scheduled.receipts(project, ident)})


@router.post('/schedules/tick')
def tick_schedules():
    return schedule_boundary(lambda: {'completed': scheduled.tick(), 'enqueued': scheduled.deliver()})


class AdoptionApproval(BaseModel):
    revision: str = Field(min_length=1, max_length=128)


@router.get('')
def inventory():
    return {'automations': supervisor.inventory(),
            'notice': 'Only explicitly connected adapters appear. Existing timers remain until their replacements pass checks.'}


@router.post('/{ident}/approve')
def approve(ident: str, request: AdoptionApproval):
    try:
        return supervisor.approve(ident, request.revision)
    except (KeyError, ValueError) as error:
        raise HTTPException(409, str(error)) from error


@router.post('/{ident}/report')
def report(ident: str):
    record = next((item for item in supervisor.inventory() if item['id'] == ident), None)
    if record is None:
        raise HTTPException(404, 'Unknown automation')
    engine.events.publish('automation.status', {key: record[key] for key in
        ('id', 'owner', 'status', 'attempts', 'last_failure')})
    return {'recorded': True}
