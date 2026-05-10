from backend.swarm.task_queue import TaskQueue
from backend.swarm.workload_balancer import WorkloadBalancer
from backend.swarm.scoring import SwarmScoring

class SwarmEngine:

    def __init__(self):
        self.queue = TaskQueue()
        self.balancer = WorkloadBalancer()
        self.scoring = SwarmScoring()

    def submit_task(self, task):
        self.queue.add(task)

    def process(self):
        task = self.queue.next()

        if not task:
            return None

        knight = self.balancer.select_knight(task)

        score = self.scoring.score_task(task)

        return {
            "task": task,
            "assigned_to": knight,
            "score": score
        }
