from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import router
from backend.websocket import ws_router
from backend.state import STATE
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Kingdom v1TAS",
    version=STATE.get("version", "1.0.0")
)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, _exception):
    # Pydantic's default response includes rejected input, which may contain secrets.
    return JSONResponse(status_code=422, content={"detail": "Invalid request format; check required fields and types"})

import os

raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8000,app://.")
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
from backend.skills.portable_api import router as portable_router, initialize
from backend.api import engine, lifecycle_manager
initialize(engine, lifecycle_manager)
app.include_router(portable_router)
from backend.integrations.discord_ai_map.http import router as discord_router, initialize as initialize_discord
from backend.skills.portable_api import service as portable_service, linker as discord_linker
initialize_discord(portable_service, discord_linker)
app.include_router(discord_router)
app.include_router(ws_router)

# Serve built frontend static assets if available
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_frontend_index():
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "Kingdom Backend Operational"}

if __name__ == "__main__":
    import sys
    import uvicorn

    host = "127.0.0.1"
    port = 8000

    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]

    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    uvicorn.run(app, host=host, port=port)
