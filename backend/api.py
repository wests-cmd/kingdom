from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.runtime.engine import RuntimeEngine

router = APIRouter()
engine = RuntimeEngine()


class TaskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModeRequest(BaseModel):
    mode: str


class ModelRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    model: str | None = None
    provider: str | None = None


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0)


class MapRequest(BaseModel):
    graph: dict[str, Any]


@router.get("/status")
def runtime_status():
    return engine.status()


@router.post("/start")
async def start():
    return await engine.start()


@router.post("/stop")
async def stop():
    return await engine.stop()


@router.get("/mode")
def mode():
    return {"mode": engine.get_mode()}


@router.put("/mode")
def set_mode(request: ModeRequest):
    try:
        return engine.set_mode(request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(request: TaskRequest):
    return engine.submit_task(request.prompt, request.metadata)


@router.get("/tasks")
def list_tasks(task_status: str | None = Query(default=None, alias="status")):
    return engine.tasks.list(task_status)


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = engine.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    try:
        return engine.cancel_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/events")
def event_history(limit: int = Query(default=50, ge=1, le=200)):
    return engine.events.history(limit)


@router.get("/knights")
def knights():
    return engine.swarm.status()


@router.get("/models")
async def model_health():
    return await engine.models.health()


@router.post("/models/generate")
async def generate(request: ModelRequest):
    try:
        return await engine.models.generate(request.prompt, request.model, request.provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/models/stream")
async def stream(request: ModelRequest):
    provider = request.provider or engine.models.default_provider
    if provider != "ollama":
        raise HTTPException(status_code=503, detail="Streaming currently requires the Ollama provider")

    async def events():
        async for token in engine.models.stream(request.prompt, request.model, provider):
            yield f"data: {token}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/memory")
def memory_entries(limit: int = Query(default=100, ge=1, le=500)):
    return engine.memory.entries(limit)


@router.post("/memory", status_code=status.HTTP_201_CREATED)
def add_memory(request: MemoryRequest):
    entry = engine.memory.add(request.content, request.metadata, request.weight)
    engine.events.publish("memory.recorded", {"entry_id": entry["id"]})
    return entry


@router.get("/memory/search")
def search_memory(query: str = Query(min_length=1), limit: int = Query(default=5, ge=1, le=50)):
    return engine.memory.search(query, limit)


@router.get("/memory/graph")
def memory_graph():
    return engine.memory.graph()


@router.post("/memory/snapshot", status_code=status.HTTP_201_CREATED)
def memory_snapshot():
    return {"path": engine.memory.snapshot()}


@router.get("/maps")
def list_maps():
    return engine.maps.list()


@router.post("/maps/{name}", status_code=status.HTTP_201_CREATED)
def export_map(name: str, request: MapRequest):
    try:
        return {"path": engine.maps.export(name, request.graph)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/maps/{name}")
def import_map(name: str):
    try:
        return engine.maps.load(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
