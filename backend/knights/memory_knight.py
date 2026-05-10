from backend.knights.base_knight import BaseKnight

class MemoryKnight(BaseKnight):

    def __init__(self):
        super().__init__("memory")
