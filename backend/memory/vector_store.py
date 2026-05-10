class VectorStore:

    def __init__(self):
        self.vectors = []

    def add(self, embedding, metadata=None):

        self.vectors.append({
            "embedding": embedding,
            "metadata": metadata or {}
        })

    def search(self, embedding):

        if not self.vectors:
            return []

        return self.vectors[:5]
