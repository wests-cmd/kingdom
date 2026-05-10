from backend.routing.model_router import ModelRouter
from backend.routing.performance_router import PerformanceRouter

class HybridRouter:

    def __init__(self):
        self.model_router = ModelRouter()
        self.performance_router = PerformanceRouter()

    def select(self, task, models):

        preferred = self.model_router.route(task)
        best = self.performance_router.choose(models)

        return {
            "preferred": preferred,
            "best_runtime": best
        }
