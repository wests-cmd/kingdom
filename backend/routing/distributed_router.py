class DistributedRouter:

    def distribute(self, nodes, task):

        if not nodes:
            return None

        return nodes[0]
