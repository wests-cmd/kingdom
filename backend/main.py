from fastapi import FastAPI
from backend.api import router
from backend.websocket import ws_router

app = FastAPI(title="Kingdom v40.1")

app.include_router(router)
app.include_router(ws_router)
