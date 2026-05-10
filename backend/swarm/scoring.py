class SwarmScoring:

    def score_task(self, task):
        complexity = len(str(task))

        if complexity < 50:
            return "low"

        if complexity < 200:
            return "medium"

        return "high"
