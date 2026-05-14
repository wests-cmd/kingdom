class ZeroTrust:

    def validate(self, actor):

        return {
            "actor": actor,
            "trusted": False
        }
