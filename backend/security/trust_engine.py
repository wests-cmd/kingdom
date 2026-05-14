class TrustEngine:

    def score(self, node):

        trust = 0.5

        if node.get("verified"):
            trust += 0.4

        return min(trust, 1.0)
