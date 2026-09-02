import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.events.event_bus import event_bus

ws_router = APIRouter()

active_connections: list[WebSocket] = []

def broadcast_event_sync(event):
    for ws in list(active_connections):
        try:
            asyncio.create_task(ws.send_json({"type": "event", "data": event}))
        except Exception:
            pass

# Subscribe websocket broadcaster to EventBus
event_bus.subscribe(broadcast_event_sync)

@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_connections.append(ws)

    try:
        while True:
            # Send periodic heartbeat keepalive
            await ws.send_json({
                "type": "heartbeat",
                "status": "alive"
            })
            await asyncio.sleep(5)
    except (WebSocketDisconnect, Exception):
        if ws in active_connections:
            active_connections.remove(ws)
