from copy import deepcopy
from agents.simple_reflex import SimpleReflexAgent


class ModelBasedAgent(SimpleReflexAgent):
    name = "Model-Based Reflex"

    def __init__(self, stale_after=15.0):
        self.stale_after = stale_after
        self.reset()

    def reset(self, config=None):
        self.state = {"route_beliefs": {}, "last_action": None}

    def debug(self):
        return deepcopy(self.state)

    def decide(self, p):
        belief_percept = deepcopy(p)
        changes = []
        for route in belief_percept["routes"]:
            key = route["route_id"]
            prior = self.state["route_beliefs"].get(key)
            if route["traffic"] is not None:
                if prior is None or prior["traffic"] != route["traffic"]:
                    changes.append(f"{key}: observed {route['traffic']} traffic")
                self.state["route_beliefs"][key] = {
                    "traffic": route["traffic"], "traffic_multiplier": route["traffic_multiplier"],
                    "observed_at": p["time"],
                }
            elif prior and p["time"] - prior["observed_at"] <= self.stale_after:
                route.update({k: prior[k] for k in ("traffic", "traffic_multiplier")})
                changes.append(f"{key}: retained {prior['traffic']} traffic from minute {prior['observed_at']}")
            elif prior:
                changes.append(f"{key}: remembered observation expired")
                self.state["route_beliefs"].pop(key)
        for key in ("status", "current_route", "progress", "weather", "time"):
            self.state[key] = p[key]
        decision = super().decide(belief_percept)
        decision.evidence.update({"belief_updates": changes, "internal_state": self.debug()})
        self.state["last_action"] = decision.action.kind
        return decision
