class DiscordAIMapExchange:

    def package(self, graph):

        return {
            "shared": True,
            "nodes": len(graph.get("nodes", []))
        }
