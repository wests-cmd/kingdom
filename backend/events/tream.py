class Stream:

    def __init__(self):
        self.stream = []

    def push(self, item):
        self.stream.append(item)

    def read(self):
        return self.stream
