from agents.base import BaseAgent
from core.metrics import route_scores


class UtilityBasedAgent(BaseAgent):
    name = "Utility-Based"

    def __init__(self, weights=None):
        if weights is not None and (len(weights) != 4 or any(w < 0 for w in weights) or abs(sum(weights) - 1) > 1e-7):
            raise ValueError("Four nonnegative utility weights must sum to one.")
        self.weights = weights

    def decide(self, p):
        common = self.lifecycle(p)
        if common:
            return common
        failure = self.guard(p)
        if failure:
            return failure
        if p["status"] == "ACCEPTED" or p["at_junction"]:
            rows = route_scores(p, self.weights)
            chosen = min(rows, key=lambda row: (-row["utility"], row["route_id"]))
            current = next((row for row in rows if row["route_id"] == p["current_route"]), None)
            if current and chosen["utility"] - current["utility"] <= 0.03:
                return self.decision("MOVE", "Keep the current route; switching benefit is below the 0.03 threshold.", scores=rows)
            if p["status"] == "ACCEPTED" or chosen["route_id"] != p["current_route"]:
                return self.select(p, chosen["route_id"], "Select the route with the greatest predicted utility.",
                                   scores=rows, weights=self.weights or ([.6, .15, .1, .15] if p["urgent"] else [.45, .25, .15, .15]))
        return self.move()
