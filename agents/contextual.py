from agents.base import BaseAgent
from core.metrics import predicted_total


class ContextualAgent(BaseAgent):
    name = "Contextual"

    def decide(self, p):
        common = self.lifecycle(p)
        if common:
            common.evidence["collected_context"] = dict(p["context"])
            return common
        failure = self.guard(p)
        if failure:
            return failure
        if p["status"] == "ACCEPTED" or p["at_junction"]:
            available = [r for r in p["routes"] if r["available"]]
            candidates, filters = available, []
            if p["context"].get("time_of_day") == "night":
                candidates = [r for r in candidates if r["well_lit"]]
                filters.append("Night: require a well-lit route.")
            if p["weather"] == "rain":
                candidates = [r for r in candidates if r["flood_risk"] < 0.7]
                filters.append("Rain: exclude routes with flood risk >= 0.7.")
            if not candidates:
                return self.decision("REPORT_FAILURE", "No available route satisfies the contextual safety constraints.",
                                     context=p["context"], filters=filters)
            sensitive = p["context"].get("food_type") in {"hot", "frozen"}
            economy = p["context"].get("customer_preference") == "economy" and not sensitive and not p["urgent"]
            if economy:
                chosen = min(candidates, key=lambda r: (r["cost"], r["route_id"]))
                filters.append("Economy preference: choose the cheapest eligible route.")
            else:
                chosen = self.fastest(p, candidates)
                filters.append("Temperature-sensitive/urgent/standard service: choose the fastest eligible route.")
            evidence = {"context": dict(p["context"]), "filters": filters,
                        "eligible_routes": [r["route_id"] for r in candidates],
                        "estimated_completion": predicted_total(p, chosen, p["current_route"] not in {None, chosen["route_id"]})}
            current = next((r for r in candidates if r["route_id"] == p["current_route"]), None)
            if p["status"] == "ACCEPTED" or current is None:
                return self.select(p, chosen["route_id"], "Use collected context to filter and select the route.", **evidence)
            return self.decision("MOVE", "The current route remains appropriate for the collected context.", **evidence)
        return self.move()
