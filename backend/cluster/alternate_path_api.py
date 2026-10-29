"""Owner opt-in configuration and bounded independent signed control probes."""
import asyncio
import threading
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/peer-paths', dependencies=[Depends(require_owner)])
_service = None
_guard = threading.Lock()


def service():
    global _service
    with _guard:
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


class BluetoothAdapter(BaseModel):
    path: str
    address: str | None
    powered: bool


class PANLink(BaseModel):
    interface: str
    device_address: str | None
    adapter: str | None


class BluetoothStatus(BaseModel):
    platform: str
    observed_at: float
    adapters: list[BluetoothAdapter]
    pan_links: list[PANLink]
    available: bool
    adapter_state: Literal['unknown', 'absent', 'off', 'on']
    reason: str


class ConfiguredPath(Path):
    transport_evidence: Literal['owner_configured_not_radio_observed']


class PathsState(BaseModel):
    peer: str
    revision: int
    fingerprint: str | None = None
    paths: list[ConfiguredPath]


class PANRoute(BaseModel):
    interface: str
    device_address: str | None
    local_address: str
    observed_at: float
    evidence: Literal['bluez_network1_and_os_route_observed']


class ProbeReceipt(BaseModel):
    path: str
    status: Literal['not_sent', 'outcome_unknown', 'verified_control_exchange']
    id: str | None = None
    peer: str | None = None
    reason: str | None = None
    transport_hint: Literal['lan', 'bluetooth_pan'] | None = None
    transport_evidence: Literal['owner_configured_not_radio_observed', 'bluez_network1_and_os_route_observed'] | None = None
    route_observation: PANRoute | None = None
    request_id: str | None = None
    response_id: str | None = None
    elapsed_ms: float | None = None
    observed_at: float | None = None
    scope: str | None = None


@router.get('/bluetooth/status', response_model=BluetoothStatus)
async def bluetooth_status():
    from backend.cluster.bluetooth_pan import observe
    return await asyncio.to_thread(observe)


@router.get('/{peer}', response_model=PathsState, response_model_exclude_none=True)
def get(peer: str):
    try:
        return service().get(peer)
    except (ValueError, KeyError) as error:
        raise HTTPException(409, 'Peer or path unavailable; inspect current owner configuration') from error


@router.put('/{peer}', response_model=PathsState, response_model_exclude_none=True)
def configure(peer: str, request: Configuration):
    try:
        return service().configure(peer, [p.model_dump() for p in request.paths], request.expected_revision)
    except (ValueError, KeyError) as error:
        raise HTTPException(409, 'Invalid or changed peer paths; use explicit local IP paths and current revision') from error


@router.post('/{peer}/probe', response_model=list[ProbeReceipt], response_model_exclude_none=True)
async def probe(peer: str, request: Batch):
    selected = await asyncio.to_thread(service)
    async def one(item):
        try:
            return await selected.probe(peer, item.key, item.path)
        except (ValueError, KeyError):
            return {'path': item.path, 'status': 'not_sent', 'reason': 'Unknown, changed or restricted path; no automatic retry authorized'}
    return await asyncio.gather(*(one(p) for p in request.probes))
