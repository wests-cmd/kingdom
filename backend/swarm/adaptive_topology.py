class AdaptiveTopology:

    def choose(self, node_count):

        if node_count < 3:
            return "direct"

        if node_count < 10:
            return "mesh"

        return "clustered"
