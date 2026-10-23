from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from typing import Literal
import subprocess
from backend.security.http_auth import require_owner
from backend.runtime.service_nodes import ServiceNode,ServiceNodes
router=APIRouter(prefix='/service-nodes',dependencies=[Depends(require_owner)])

@router.get('/discovery')
def discovery():
    from backend.runtime.service_discovery import discover_local_services
    return {**discover_local_services(),'notice':'Observed service scopes only; discovery grants no control or update permissions.'}
def service():
    from backend.api import engine
    from backend.storage.db import db
    return ServiceNodes(engine,db)
class Action(BaseModel):
    unit:str
    action:Literal['start','stop','restart']
@router.get('')
def nodes(): return service().list()
@router.put('/{ident}')
def save(ident:str,request:ServiceNode):
    try:return service().save(ident,request)
    except ValueError as error:raise HTTPException(400,str(error)) from error
@router.get('/{ident}/inspect')
def inspect(ident:str):
    try:return service().inspect(ident)
    except (ValueError,TimeoutError,subprocess.SubprocessError,OSError) as error:raise HTTPException(502,'Service inspection unavailable; check the connection and pinned SSH host key') from error
@router.post('/{ident}/actions',status_code=201)
def action(ident:str,request:Action):
    try:return service().action(ident,request.unit,request.action)
    except ValueError as error:raise HTTPException(400,str(error)) from error
