import subprocess

class SecurityNode:
    def __init__(self):
        self.alerts = []

    def check_logs(self):
        logs = subprocess.getoutput("journalctl -n 50")
        if "error" in logs.lower():
            self.alerts.append("Error detected in logs.")
        return logs

    def check_processes(self):
        procs = subprocess.getoutput("ps aux")
        suspicious = [p for p in procs.split("\n") if "unknown" in p.lower()]
        if suspicious:
            self.alerts.append("Suspicious processes detected.")
        return suspicious

    def run_security_cycle(self):
        self.alerts = []
        self.check_logs()
        self.check_processes()
        return self.alerts
