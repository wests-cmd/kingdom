class SharedGraph:

    def __init__(self):
        self.shared = {
            "nodes": [],
            "edges": []
        }

    def merge(self, graph):

        self.shared["nodes"].extend(
            graph.get("nodes", [])
        )

        self.shared["edges"].extend(
            graph.get("edges", [])
        )

    def export(self):
        return self.shared
