from system.swarm import Swarm
from system.debate import Debate
from system.market import Market
from system.memory import Memory
from system.timeline import Timeline

class Orchestrator:
    def __init__(self, queue):
        self.queue = queue
        self.swarm = Swarm()
        self.debate = Debate()
        self.market = Market()
        self.memory = Memory()
        self.timeline = Timeline()

    def process(self, task, knights):
        swarm = self.swarm.form(knights)

        plans = self.debate.generate(task, swarm)
        best_plan = self.debate.select(plans)

        bids = self.market.collect(swarm, task)
        winner = self.market.select(bids)

        self.timeline.record(task, winner)

        return {
            "task": task,
            "plan": best_plan,
            "assigned": winner
        }

    def handle_result(self, data):
        self.memory.store(data)
        self.timeline.update(data)
