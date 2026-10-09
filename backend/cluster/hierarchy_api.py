from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.security.http_auth import require_owner
from backend.cluster.node_registry import node_registry
from backend.cluster.hierarchy import CommandHierarchy
from backend.storage.db import db
from backend.api import engine

router = APIRouter(prefix='/hierarchy', dependencies=[Depends(require_owner)])
hierarchy = CommandHierarchy(db, node_registry, engine.events.publish)


class GroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    captain: str = Field(max_length=128)
    members: list[str] = Field(min_length=1, max_length=100)


@router.get('')
def status(): return hierarchy.export(engine.swarm.registry.status())


@router.post('/groups')
def create(request: GroupRequest):
    try: return hierarchy.create_group(request.name, request.captain, request.members)
    except ValueError as error: raise HTTPException(400, str(error)) from error
