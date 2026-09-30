import asyncio
import anyio
import os
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from backend.api import engine
from backend.security.http_auth import owner_auth

ws_router = APIRouter()

@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin")
    allowed = set(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","))
    allowed.add(("https" if ws.url.scheme == "wss" else "http") + "://" + ws.url.netloc)
    try:
        owner_auth.authenticate(ws.cookies.get("kingdom_session"))
        if origin and origin not in allowed:
            raise HTTPException(status_code=403)
    except HTTPException:
        await ws.close(code=1008)
        return
    await ws.accept()
    queue = engine.events.subscribe()
    async def send_events():
        await ws.send_json({"type": "runtime.snapshot", "data": engine.status()})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "heartbeat", "data": engine.status()})
    async def receive_disconnect():
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
    tasks = [asyncio.create_task(send_events()), asyncio.create_task(receive_disconnect())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        for task in tasks:
            task.cancel()
        with anyio.CancelScope(shield=True):
            await asyncio.gather(*tasks, return_exceptions=True)
        engine.events.unsubscribe(queue)
