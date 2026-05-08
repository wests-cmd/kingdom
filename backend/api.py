from fastapi import APIRouter
from backend.runtime.engine import RuntimeEngine

router = APIRouter()
engine = RuntimeEngine()

@router.get("/status")
def status():
    return engine.status()

@router.post("/start")
def start():
    return engine.start()

@router.post("/stop")
def stop():
    return engine.stop()

@router.get("/mode")
def mode():
    return engine.get_mode()
