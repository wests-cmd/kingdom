from backend.security.injection_detector import InjectionDetector


class PromptFirewallException(Exception):
    """Custom exception raised when a prompt fails security firewall inspection."""
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
