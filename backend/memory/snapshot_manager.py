import json
import time
from pathlib import Path

SNAPSHOT_PATH = Path("data/snapshots")

class SnapshotManager:

    def create(self, data):

        SNAPSHOT_PATH.mkdir(
            parents=True,
            exist_ok=True
        )

        name = f"{int(time.time())}.json"

        path = SNAPSHOT_PATH / name

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        return str(path)
