from backend.security.injection_detector import InjectionDetector

class PromptFirewall:

    def __init__(self):
        self.detector = InjectionDetector()

    def inspect(self, prompt):

        result = self.detector.analyze(prompt)

        if result["blocked"]:
            raise Exception(
                f"Prompt blocked: {result['reason']}"
            )

        return True
