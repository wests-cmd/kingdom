class ApprovalEngine:

    def requires_approval(self, severity):

        return severity in [
            "critical",
            "destructive"
        ]
