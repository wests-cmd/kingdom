class MindsLoop:
    def __init__(self):
        self.memory = []

    def store(self, data, confidence):
        if confidence > 0.7:
            self.memory.append(data)
