import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api import engine

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    queue = engine.events.subscribe()
    await ws.send_json({"type": "runtime.snapshot", "data": engine.status()})
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "heartbeat", "data": engine.status()})
    except WebSocketDisconnect:
        pass
    finally:
        engine.events.unsubscribe(queue)
