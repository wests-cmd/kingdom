class MindsLoop:

    def evaluate(self, task, outcomes):

        result = {
            "task": task,
            "success_count": len(outcomes),
            "confidence": 0.0
        }

        if outcomes:
            result["confidence"] = sum(
                o.get("confidence", 0.5)
                for o in outcomes
            ) / len(outcomes)

        return result
