import subprocess

def scan_local_ips():
    try:
        output = subprocess.getoutput("hostname -I")
        return output.split()
    except Exception:
        return []
