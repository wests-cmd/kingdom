from backend.state import STATE

class RuntimeEngine:

    def initialize(self):
        STATE["running"] = True

    def start(self):
        STATE["running"] = True
        return {"status": "started"}

    def stop(self):
        STATE["running"] = False
        return {"status": "stopped"}

    def status(self):
        return STATE

    def get_mode(self):
        return STATE["mode"]
