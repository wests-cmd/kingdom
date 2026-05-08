from fastapi import APIRouter, WebSocket
import asyncio

ws_router = APIRouter()

clients = []

@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)

    try:
        while True:
            await ws.send_json({
                "type": "heartbeat",
                "status": "alive"
            })
            await asyncio.sleep(1)
    except:
        clients.remove(ws)
