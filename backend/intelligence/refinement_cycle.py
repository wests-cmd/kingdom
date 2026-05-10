class RefinementCycle:

    def refine(self, idea, scores):

        total = sum(scores)

        if total <= 8:
            return {
                "status": "accepted",
                "next": ".01 refinement"
            }

        if total <= 12:
            return {
                "status": "maybe",
                "next": "re-evaluate"
            }

        return {
            "status": "rejected"
        }
