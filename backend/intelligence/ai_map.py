import json
import re
from pathlib import Path

AI_MAP_PATH = Path("data/ai_maps")
VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

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
        # Optimization: Use precompiled regex matching instead of character-by-character string scanning
        if not name or Path(name).name != name or not VALID_NAME_RE.match(name):
            raise ValueError("Map name must use only letters, numbers, underscores, or hyphens")
