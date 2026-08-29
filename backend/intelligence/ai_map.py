import json
from pathlib import Path

AI_MAP_PATH = Path("data/ai_maps")

class AIMap:

    def export(self, name, graph):

        self._validate_name(name)

        AI_MAP_PATH.mkdir(parents=True, exist_ok=True)

        path = AI_MAP_PATH / f"{name}.json"

        with open(path, "w") as f:
            json.dump(graph, f, indent=2)

        return str(path)

    def load(self, name):

        self._validate_name(name)

        path = AI_MAP_PATH / f"{name}.json"

        if not path.exists():
            return {}

        with open(path, "r") as f:
            return json.load(f)

    def list(self):
        AI_MAP_PATH.mkdir(parents=True, exist_ok=True)
        return sorted(path.stem for path in AI_MAP_PATH.glob("*.json"))

    def _validate_name(self, name):
        if not name or Path(name).name != name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in name):
            raise ValueError("Map name must use only letters, numbers, underscores, or hyphens")
