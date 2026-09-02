import json
from pathlib import Path

AI_MAP_PATH = Path("data/ai_maps")

class AIMap:

    def export(self, name, graph):

        AI_MAP_PATH.mkdir(parents=True, exist_ok=True)

        path = AI_MAP_PATH / f"{name}.json"

        with open(path, "w") as f:
            json.dump(graph, f, indent=2)

        return str(path)

    def load(self, name):

        path = AI_MAP_PATH / f"{name}.json"

        if not path.exists():
            return {}

        with open(path, "r") as f:
            return json.load(f)
