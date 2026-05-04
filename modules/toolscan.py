import shutil

def scan():
    tools = ["python", "git", "docker"]
    return {t: bool(shutil.which(t)) for t in tools}
