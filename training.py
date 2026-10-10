from agents.learning import LearningAgent
from core.metrics import reward_for
from core.runner import DeliveryRun


def train(scenarios, samples_per_route=20, policy=None, seed=1000):
    """Balanced exploratory coverage; evaluation is always separate and frozen."""
    if not 1 <= samples_per_route <= 100:
        raise ValueError("Samples per route must be between 1 and 100.")
    agent = LearningAgent(policy=policy, training=True)
    records = []
    for sample in range(samples_per_route):
        for scenario in scenarios:
            for route in scenario.routes:
                if not route.available:
                    continue
                config = scenario.clone()
                config.noise = True
                config.seed = seed + sample
                agent.forced_route = route.route_id
                run = DeliveryRun(config, "Learning", agent).complete()
                reward = reward_for(run.env.outcome(), config, route.route_id)
                agent.observe_reward(reward)
                records.append({"episode": len(records) + 1, "scenario": config.scenario_id,
                                "context": agent.selected_context, "route": route.route_id,
                                "reward": reward, "seed": config.seed, **run.env.outcome()})
    return agent.policy(), records


def evaluate(scenarios, policy, repeats=10, seed=9000):
    records = []
    for i in range(repeats):
        for scenario in scenarios:
            config = scenario.clone()
            config.noise = True
            config.seed = seed + i
            for label, snapshot in [("Cold start", None), ("Trained", policy)]:
                agent = LearningAgent(policy=snapshot, training=False)
                run = DeliveryRun(config, "Learning", agent).complete()
                records.append({"policy": label, "scenario": config.scenario_id, "seed": config.seed,
                                "reward": reward_for(run.env.outcome(), config, agent.selected_route),
                                **run.env.outcome()})
    return records
