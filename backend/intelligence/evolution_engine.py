class EvolutionEngine:

    def evolve(self, metrics):

        score = metrics.get("success_rate", 0)

        if score > 0.9:
            return "optimize"

        if score < 0.5:
            return "restructure"

        return "stable"
