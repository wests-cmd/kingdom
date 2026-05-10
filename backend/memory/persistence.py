import json
from pathlib import Path

DATA_PATH = Path("data/memory")

class Persistence:

    def save(self, name, data):

        DATA_PATH.mkdir(parents=True, exist_ok=True)

        path = DATA_PATH / f"{name}.json"

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, name):

        path = DATA_PATH / f"{name}.json"

        if not path.exists():
            return {}

        with open(path, "r") as f:
            return json.load(f)
