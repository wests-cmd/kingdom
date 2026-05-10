class WeightedMemory:

    def __init__(self):
        self.memories = []

    def add(self, content, weight=1.0):

        self.memories.append({
            "content": content,
            "weight": weight
        })

    def top(self, limit=5):

        ranked = sorted(
            self.memories,
            key=lambda x: x["weight"],
            reverse=True
        )

        return ranked[:limit]
