class IntelligenceGraph:

    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, node):
        self.nodes.append(node)

    def add_edge(self, source, target):

        self.edges.append({
            "source": source,
            "target": target
        })

    def export(self):

        return {
            "nodes": self.nodes,
            "edges": self.edges
        }
