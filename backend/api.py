from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.runtime.engine import RuntimeEngine

router = APIRouter()
engine = RuntimeEngine()


class TaskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
