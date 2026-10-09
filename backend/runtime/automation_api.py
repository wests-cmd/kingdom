from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.security.http_auth import require_owner
from backend.storage.db import db
from backend.api import engine
from backend.runtime.automation import AutomationSupervisor
from backend.runtime.workshop_adapter import WorkshopAdapter
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
