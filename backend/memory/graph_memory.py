class GraphMemory:

    def __init__(self):
        self.graph = {
            "nodes": [],
            "edges": []
        }

    def add_memory(self, node):

        self.graph["nodes"].append(node)

    def relate(self, source, target):

        self.graph["edges"].append({
            "source": source,
            "target": target
        })

    def export(self):
        return self.graph
