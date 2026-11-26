"""Owner-authenticated observational work projection, never a dispatch surface."""
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.security.http_auth import require_owner
from backend.runtime.work_projection import project_work

router=APIRouter(prefix="/work",dependencies=[Depends(require_owner)])


@router.get("/overview")
def overview(project_scope:str|None=Query(default=None,min_length=1,max_length=200),
             session_scope:str|None=Query(default=None,min_length=1,max_length=100),
             limit:int=Query(default=100,ge=1,le=100)):
    from backend.storage.db import db
    try:
        return project_work(db,project_scope=project_scope,session_scope=session_scope,limit=limit)
    except ValueError as error:
        raise HTTPException(400,"Invalid scope or unavailable work projection") from error
