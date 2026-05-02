import shutil

class ToolScan:
    def scan(self):
        tools = {}
        for tool in ["python3", "docker", "git", "ffmpeg", "nmap"]:
            path = shutil.which(tool)
            if path:
                tools[tool] = {"path": path, "known": True}
        return tools
