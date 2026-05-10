class PerformanceRouter:

    def choose(self, models):

        ranked = sorted(
            models,
            key=lambda x: x["latency"]
        )

        return ranked[0]
