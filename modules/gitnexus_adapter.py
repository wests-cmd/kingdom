import subprocess

class GitNexusAdapter:
    def status(self):
        try:
            return subprocess.getoutput("git status --short")
        except Exception as e:
            return f"git status error: {e}"
