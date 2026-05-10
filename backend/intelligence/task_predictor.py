class TaskPredictor:

    def predict(self, task):

        size = len(str(task))

        if size < 50:
            return {
                "complexity": "low",
                "recommended_knights": 1
            }

        if size < 200:
            return {
                "complexity": "medium",
                "recommended_knights": 3
            }

        return {
            "complexity": "high",
            "recommended_knights": 5
        }
