class SlidingWindow:

    def __init__(self, size=4096):
        self.size = size

    def trim(self, tokens):

        if len(tokens) <= self.size:
            return tokens

        return tokens[-self.size:]
