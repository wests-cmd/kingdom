"""Owner opt-in configuration and bounded independent signed control probes."""
import asyncio
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/peer-paths', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.cluster.node_registry import node_registry
        from backend.cluster.identity import KingdomIdentity
        from backend.events.event_bus import event_bus
        from backend.cluster.alternate_paths import AlternatePaths
        _service = AlternatePaths(db, node_registry, KingdomIdentity.get_or_create(), event_bus)
    return _service


class Path(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    endpoint: str = Field(min_length=1, max_length=200)
    transport_hint: Literal['lan', 'bluetooth_pan']


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    paths: list[Path] = Field(max_length=2)
    expected_revision: int = Field(ge=0)


class Probe(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    key: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    path: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')


class Batch(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    probes: list[Probe] = Field(min_length=1, max_length=8)


@router.get('/{peer}')
def get(peer: str):
    try:
        return service().get(peer)
    except (ValueError, KeyError) as error:
        raise HTTPException(409, 'Peer or path unavailable; inspect current owner configuration') from error


@router.put('/{peer}')
def configure(peer: str, request: Configuration):
    try:
        return service().configure(peer, [p.model_dump() for p in request.paths], request.expected_revision)
    except (ValueError, KeyError) as error:
        raise HTTPException(409, 'Invalid or changed peer paths; use explicit local IP paths and current revision') from error


@router.post('/{peer}/probe')
async def probe(peer: str, request: Batch):
    async def one(item):
        try:
            return await service().probe(peer, item.key, item.path)
        except (ValueError, KeyError):
            return {'path': item.path, 'status': 'not_sent', 'reason': 'Unknown, changed or restricted path; no automatic retry authorized'}
    return await asyncio.gather(*(one(p) for p in request.probes))
