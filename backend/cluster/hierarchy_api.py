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


class TopologyRequest(BaseModel):
    version: int = Field(ge=0, strict=True)
    parents: dict[str, str] = Field(max_length=1000)


@router.put('/topology')
def save_topology(request: TopologyRequest):
    from backend.cluster.topology import TopologyConflict
    nodes = hierarchy.export(engine.swarm.registry.status())['topology']['nodes']
    try:
        return hierarchy.topology.save(request.version, request.parents, nodes)
    except TopologyConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


from backend.cluster.release_status import DesiredRelease, ReleasePreferences
release_preferences = ReleasePreferences(db, engine.events.publish)


@router.get('/releases')
def release_status():
    return release_preferences.status([node.to_dict() for node in hierarchy.computers()])


@router.put('/releases/desired')
def desired_release(request: DesiredRelease):
    return release_preferences.set(request.model_dump())
