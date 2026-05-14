class FailureClassifier:

    def classify(self, error):

        text = str(error).lower()

        if "memory" in text:
            return "memory"

        if "network" in text:
            return "network"

        return "general"
