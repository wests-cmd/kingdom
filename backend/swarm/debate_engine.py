class DebateEngine:

    def evaluate(self, responses):
        ranked = sorted(
            responses,
            key=lambda r: r.get("confidence", 0),
            reverse=True
        )

        return ranked[0] if ranked else None
