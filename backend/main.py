from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import router
from backend.websocket import ws_router
from backend.state import STATE
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    import asyncio
    if await asyncio.to_thread(engine.autostart_requested):
        await engine.start(persist=False)
    await schedule_runner.start()
    await programme_runner.start()
    await boss_runner.start()
    await backlog_runner.start()
    await problem_runner.start()
    await jules_runner.start()
    await peer_connections.start()
    try:
        yield
    finally:
        from backend.runtime.request_api import background
        await background.stop()
        await peer_connections.stop()
        await jules_runner.stop()
        await problem_runner.stop()
        await programme_runner.stop()
        await boss_runner.stop()
        await backlog_runner.stop()
        await schedule_runner.stop()
        await engine.stop(persist=False)

app = FastAPI(
    title="Kingdom v1TAS",
    version=STATE.get("version", "1.0.0"), lifespan=lifespan
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
from backend.security.local_access import router as local_access_router
app.include_router(local_access_router)
from backend.runtime.automation_api import router as automation_router
app.include_router(automation_router)
from backend.runtime.workspace_api import router as workspace_router
app.include_router(workspace_router)
from backend.runtime.mission_api import router as mission_router
app.include_router(mission_router)
from backend.cluster.hierarchy_api import router as hierarchy_router
app.include_router(hierarchy_router)
from backend.cluster.federation_api import router as federation_router, peer_connections
app.include_router(federation_router)
from backend.cluster.mesh_api import router as mesh_router
app.include_router(mesh_router)
from backend.cluster.alternate_path_api import router as alternate_path_router
app.include_router(alternate_path_router)
from backend.system.ui_update_api import router as ui_update_router
app.include_router(ui_update_router)
from backend.accessibility import router as accessibility_router
app.include_router(accessibility_router)
from backend.recovery import router as recovery_router
app.include_router(recovery_router)
from backend.skills.portable_api import router as portable_router, initialize
from backend.api import engine, lifecycle_manager
initialize(engine, lifecycle_manager)
app.include_router(portable_router)
from backend.integrations.discord_ai_map.http import router as discord_router, initialize as initialize_discord
from backend.skills.portable_api import service as portable_service, linker as discord_linker
initialize_discord(portable_service, discord_linker)
app.include_router(discord_router)
app.include_router(ws_router)
from backend.runtime.harness_api import router as harness_router
from backend.runtime.agent_api import router as agent_router
app.include_router(harness_router)
app.include_router(agent_router)
from backend.runtime.service_api import router as service_router
app.include_router(service_router)
from backend.runtime.knight_management_api import router as knight_management_router
app.include_router(knight_management_router)
from backend.memory.knowledge_api import router as knowledge_router, initialize as initialize_knowledge
from backend.storage.db import db as knowledge_db
initialize_knowledge(knowledge_db)
app.include_router(knowledge_router)
from backend.runtime.tool_workshop_api import router as tool_workshop_router
from backend.runtime.model_lab_api import router as model_lab_router
app.include_router(tool_workshop_router)
app.include_router(model_lab_router)
from backend.runtime.request_api import router as request_router, service as request_service
app.include_router(request_router)
from backend.runtime.chat_proposal_api import router as chat_proposal_router
app.include_router(chat_proposal_router)
from backend.runtime.orchestration_api import router as orchestration_router
app.include_router(orchestration_router)
from backend.memory.portable_vault_api import router as vault_router, initialize as initialize_vault
initialize_vault(knowledge_db, engine.events.publish)
app.include_router(vault_router)
from backend.memory.vault_sync_api import router as vault_sync_router
app.include_router(vault_sync_router)
from backend.integrations.payment_api import router as payment_router
app.include_router(payment_router)
from backend.integrations.jules_api import router as jules_router
app.include_router(jules_router)
from backend.runtime.scheduled_runner import ScheduledRunner
from backend.runtime.automation_api import scheduled
scheduled.enqueue_request = lambda body: request_service().create(body)
scheduled.cancel_request = lambda ident: request_service().cancel(ident)
schedule_runner = ScheduledRunner(scheduled, engine, requests=request_service)
from backend.runtime.work_backlog_api import router as backlog_router, service as backlog_service
from backend.runtime.work_backlog_runner import WorkBacklogRunner
app.include_router(backlog_router)
backlog_runner = WorkBacklogRunner(backlog_service, engine.events.publish)
from backend.runtime.work_programme_api import router as programme_router, service as programme_service
from backend.runtime.work_programme_runner import WorkProgrammeRunner
app.include_router(programme_router)
programme_runner = WorkProgrammeRunner(programme_service, engine.events.publish)
from backend.runtime.problem_api import router as problem_router,service as problem_service
from backend.runtime.problem_bot import ProblemBotRunner
app.include_router(problem_router)
problem_runner=ProblemBotRunner(problem_service,engine.events.publish)
from backend.integrations.jules_api import service as jules_service
from backend.integrations.jules_runner import JulesRunner
jules_runner = JulesRunner(jules_service, engine.events.publish)
from backend.runtime.boss_review_api import router as boss_router, service as boss_service
app.include_router(boss_router)
boss_runner = WorkProgrammeRunner(boss_service, engine.events.publish, name='boss')


# Serve built frontend static assets if available
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    branding_dir = os.path.join(frontend_dist, "branding")
    if os.path.exists(branding_dir):
        app.mount("/branding", StaticFiles(directory=branding_dir), name="branding")

    @app.get("/")
    def serve_frontend_index():
        from backend.system.ui_update_api import components
        selected = components()
        active = selected.status()['active']
        if active:
            candidate = selected.directory(active) / 'index.html'
            if candidate.is_file(): return FileResponse(candidate, headers={'Cache-Control':'no-store'})
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "Kingdom Backend Operational"}

    @app.get('/kingdom.webmanifest')
    def serve_web_manifest():
        return FileResponse(os.path.join(frontend_dist,'kingdom.webmanifest'),media_type='application/manifest+json',headers={'Cache-Control':'no-store'})

    @app.get('/kingdom-sw.js')
    def serve_web_worker():
        return FileResponse(os.path.join(frontend_dist,'kingdom-sw.js'),media_type='application/javascript',headers={'Cache-Control':'no-store','Service-Worker-Allowed':'/'})

    @app.get('/ui/{component}/{resource:path}')
    def serve_ui_component(component: str, resource: str):
        from backend.system.ui_update_api import components
        from fastapi import HTTPException
        try:
            target = components().asset(component, resource)
            return FileResponse(target, headers={'Cache-Control':'public, max-age=31536000, immutable'})
        except ValueError as error: raise HTTPException(404,'Component asset not found') from error

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
