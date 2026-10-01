"""A prepared attachment is not a sent Discord message."""
from backend.skills.portable import PortableSkillMap, canonical_map, map_checksum


class DiscordAIMapExchange:
    def package(self, graph):
        model = graph if isinstance(graph, PortableSkillMap) else PortableSkillMap.model_validate(graph)
        return {"shared": False, "filename": model.map_id + ".skillmap.json",
                "payload": canonical_map(model), "checksum": map_checksum(model)}
