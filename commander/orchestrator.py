from system.swarm_debate import SwarmDebate
from system.task_market import TaskMarket

debate = SwarmDebate()
market = TaskMarket()

def run(task, knights):
    swarm = knights[:3]

    plans = debate.generate(task, swarm)
    best_plan = debate.select(plans)

    bids = [market.bid(k) for k in swarm]
    winner = market.choose(bids)

    return {
        "plan": best_plan,
        "winner": winner
    }
