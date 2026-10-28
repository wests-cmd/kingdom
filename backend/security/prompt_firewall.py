from backend.security.injection_detector import InjectionDetector


class PromptFirewallException(Exception):
    """Raised when a prompt violates security policies or contains prompt injection patterns."""

    pass


class PromptFirewall:

    def __init__(self):
        self.detector = InjectionDetector()

    def inspect(self, prompt):

        result = self.detector.analyze(prompt)

        if result["blocked"]:
            raise PromptFirewallException(
                f"Prompt blocked: {result['reason']}"
            )

        return True
