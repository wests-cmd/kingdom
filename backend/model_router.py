class ModelRouter:

    def route(self, task):

        task = str(task).lower()

        if "code" in task:
            return "codellama"

        if "research" in task:
            return "mistral"

        return "llama3"
