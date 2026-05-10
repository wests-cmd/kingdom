NODES = []

class NodeRegistry:

    def register(self, node):
        NODES.append(node)

    def list(self):
        return NODES
