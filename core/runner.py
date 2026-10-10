from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from agents import AGENTS
from core.environment import DeliveryEnvironment
from core.models import Action


class DeliveryRun:
    def __init__(self, scenario, agent_name, agent=None, max_steps=1000):
        self.run_id = uuid4().hex
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.scenario = scenario.clone()
        self.agent_name = agent_name
        self.agent = agent or AGENTS[agent_name]()
        self.agent.reset(scenario.to_dict())
        self.env = DeliveryEnvironment(scenario)
        self.trace = []
        self.max_steps = max_steps
        self.policy_version = getattr(self.agent, "policy_version", None)

    def step(self):
        if self.env.terminal:
            return None
        if len(self.trace) >= self.max_steps:
            self.env.status = "TIMED_OUT"
            self.env.failure_reason = "Maximum number of decisions reached."
            self.agent.finalize(self.env.percept())
            return None
        p = self.env.percept()
        before = deepcopy(self.agent.debug())
        decision = self.agent.decide(deepcopy(p))
        error = None
        try:
            self.env.apply(decision.action)
        except ValueError as exc:
            error = str(exc)
            self.env.apply(Action("REPORT_FAILURE"))
            self.env.failure_reason = f"Invalid action: {error}"
        if self.env.terminal:
            self.agent.finalize(self.env.percept())
        event = {"step": len(self.trace) + 1, "percept": p, "decision": decision.to_dict(),
                 "state_before": before, "state_after": deepcopy(self.agent.debug()),
                 "after": self.env.percept(), "error": error,
                 "environment_events": deepcopy(self.env.event_log)}
        self.trace.append(event)
        return event

    def complete(self):
        while not self.env.terminal:
            self.step()
        return self

    def result_row(self):
        return {"run_id": self.run_id, "agent": self.agent_name, "scenario": self.scenario.scenario_id,
                "policy_version": self.policy_version or "fixed", "decisions": len(self.trace),
                **self.env.outcome()}

    def export(self):
        return {"run_id": self.run_id, "created_at": self.created_at, "agent": self.agent_name,
                "scenario": self.scenario.to_dict(), "result": self.result_row(), "trace": self.trace,
                "final_agent_state": self.agent.debug()}


def compare(scenarios, policy=None, seed=None):
    from agents.learning import LearningAgent
    runs = []
    for scenario in scenarios:
        config = scenario.clone()
        if seed is not None:
            config.seed = seed
        for name in AGENTS:
            agent = LearningAgent(policy=policy) if name == "Learning" else None
            runs.append(DeliveryRun(config, name, agent).complete())
    return runs
