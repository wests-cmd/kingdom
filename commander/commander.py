from fastapi import FastAPI
from modules.ilmfit import ILMFit
from modules.ruflo import ModelRegistry
from modules.openclaw_full import OpenClawFull
from modules.openclaw_lite import OpenClawLite
from modules.openclaw_micro import OpenClawMicro
from modules.gitnexus_adapter import GitNexusAdapter
from modules.toolscan import ToolScan
from commander.security_node import SecurityNode
from commander import ui

app = FastAPI()

ilm = ILMFit()
models = ModelRegistry()
claw_full = OpenClawFull()
claw_lite = OpenClawLite()
claw_micro = OpenClawMicro()
git = GitNexusAdapter()
toolscan = ToolScan()
security = SecurityNode()

app.include_router(ui.router)

def auto_level(caps):
    ram = caps.get("ram_gb", 0)
    if ram >= 8:
        return 1
    if ram >= 4:
        return 2
    return 3

@app.get("/status")
def status():
    return {
        "kingdom": 4,
        "capabilities": ilm.capabilities(),
        "tools": toolscan.scan(),
        "git": git.status(),
        "security_alerts": security.run_security_cycle()
    }

@app.post("/register")
def register_knight(data: dict):
    name = data.get("name", "unknown")
    caps = data.get("capabilities", {})
    requested = data.get("requested_level")

    level = auto_level(caps)
    if requested in [1, 2, 3]:
        level = requested

    return {
        "status": "registered",
        "knight": name,
        "assigned_level": level,
        "capabilities": caps
    }
