from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import router
from backend.websocket import ws_router

app = FastAPI(title="Kingdom v40.2.0")

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
app.include_router(ws_router)

# Serve built frontend static assets if available
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

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
