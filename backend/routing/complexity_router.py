class ComplexityRouter:

    def classify(self, task):

        size = len(str(task))

        if size < 50:
            return "simple"

        if size < 200:
            return "medium"

        return "complex"
