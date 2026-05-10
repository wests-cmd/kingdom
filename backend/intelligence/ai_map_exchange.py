from backend.intelligence.ai_map import AIMap

class AIMapExchange:

    def __init__(self):
        self.maps = AIMap()

    def import_map(self, name):
        return self.maps.load(name)

    def export_map(self, name, graph):
        return self.maps.export(name, graph)
