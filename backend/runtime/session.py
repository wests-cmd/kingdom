import time

class Session:
    def __init__(self):
        self.start_time = time.time()
        self.duration = 86400  # 24h
