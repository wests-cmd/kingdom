from backend.state import STATE

VERSION = STATE.get("version", "1.0.0")

def get_version():
    return STATE.get("version", "1.0.0")
