from commander.orchestrator import Orchestrator
from system.task_queue import TaskQueue
from intelligence.router import IntelligenceRouter

class Kernel:
    def __init__(self, config):
        self.config = config
        self.queue = TaskQueue()
        self.router = IntelligenceRouter(config)
        self.orchestrator = Orchestrator(self.queue, self.router)

    def start(self):
        print("Kingdom Kernel started...")

        while True:
            task = self.queue.get()

            if task:
                decision = self.router.route(task)

                self.orchestrator.execute(task, decision)
