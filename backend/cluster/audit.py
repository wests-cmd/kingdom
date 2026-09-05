import os
import json
import logging
from typing import Dict, Any, List

LOG_FILE = os.path.join("data", "cluster_audit.log")

class ClusterAuditLogger:
    def __init__(self, filepath: str = LOG_FILE):
        self.filepath = filepath
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def log_event(self, event_type: str, node_id: str, kingdom_id: str, details: Dict[str, Any], result: str = "SUCCESS"):
        import time
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "node_id": node_id,
            "kingdom_id": kingdom_id,
            "result": result,
            "details": details
        }
        with open(self.filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")

audit_logger = ClusterAuditLogger()
