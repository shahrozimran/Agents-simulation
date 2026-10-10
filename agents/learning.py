"""Tabular context-dependent route learning, separate from fixed lifecycle rules."""
from copy import deepcopy
import random
from uuid import uuid4
from agents.base import BaseAgent


class LearningAgent(BaseAgent):
    name = "Learning"
    reward_version = "utility-v1"

    def __init__(self, policy=None, training=False, epsilon=0.1, seed=42, forced_route=None):
        policy = deepcopy(policy or {})
        self.values = policy.get("values", {})
        self.policy_version = policy.get("policy_version", "cold-start")
        self.training, self.epsilon = training, epsilon
        self.rng = random.Random(seed)
        self.forced_route = forced_route
        self.reset()

    def reset(self, config=None):
        self.selected_context = self.selected_route = None
        self.feedback_applied = False

    @staticmethod
    def context_key(p):
        congestion = "heavy" if any(r["traffic"] == "heavy" for r in p["routes"]) else "normal"
        return f"{p['weather']}|{congestion}|{'urgent' if p['urgent'] else 'regular'}"

    def debug(self):
        return {"policy_version": self.policy_version, "training": self.training,
                "selected_context": self.selected_context, "values": deepcopy(self.values)}

    def policy(self):
        return {"policy_version": self.policy_version, "reward_version": self.reward_version,
                "values": deepcopy(self.values)}

    def decide(self, p):
        common = self.lifecycle(p)
        if common:
            return common
        failure = self.guard(p)
        if failure:
            return failure
        if p["status"] == "ACCEPTED":
            key = self.context_key(p)
            candidates = [r["route_id"] for r in p["routes"] if r["available"]]
            values = self.values.get(key, {})
            unseen = [r for r in candidates if values.get(r, {}).get("count", 0) == 0]
            if self.training and self.forced_route in candidates:
                chosen, strategy = self.forced_route, "scheduled exploration"
            elif self.training and unseen:
                chosen, strategy = unseen[0], "explore an unseen route"
            elif self.training and self.rng.random() < self.epsilon:
                chosen, strategy = self.rng.choice(candidates), "epsilon exploration"
            else:
                # Unknown values have a declared neutral prior of zero.
                chosen = min(candidates, key=lambda r: (-values.get(r, {}).get("q", 0.0), r))
                strategy = "exploit learned mean reward" if values else "cold-start fixed tie-break"
            self.selected_context, self.selected_route = key, chosen
            return self.select(p, chosen, strategy, context=key, values=deepcopy(values),
                               training=self.training, epsilon=self.epsilon if self.training else 0)
        if p["at_junction"]:
            current = next(r for r in p["routes"] if r["route_id"] == p["current_route"])
            if not current["available"]:
                chosen = self.fastest(p, [r for r in p["routes"] if r["available"]])
                return self.select(p, chosen["route_id"], "The learned route is closed; execute the availability fallback.")
        return self.move()

    def observe_reward(self, reward):
        if not self.training:
            raise ValueError("Frozen evaluation cannot update a policy.")
        if self.feedback_applied:
            raise ValueError("Feedback has already been applied for this delivery.")
        if self.selected_route is None:
            self.feedback_applied = True
            return
        row = self.values.setdefault(self.selected_context, {}).setdefault(self.selected_route, {"count": 0, "q": 0.0})
        row["count"] += 1
        row["q"] += (reward - row["q"]) / row["count"]
        self.policy_version = f"trained-{uuid4().hex[:12]}"
        self.feedback_applied = True
