from agents.base import BaseAgent


class SimpleReflexAgent(BaseAgent):
    name = "Simple Reflex"

    def decide(self, p):
        common = self.lifecycle(p)
        if common:
            return common
        failure = self.guard(p)
        if failure:
            return failure
        if p["status"] == "ACCEPTED" or p["at_junction"]:
            routes = [r for r in p["routes"] if r["available"]]
            current = next((r for r in routes if r["route_id"] == p["current_route"]), None)
            reference = current or routes[0]
            if reference["traffic"] == "heavy":
                chosen = next((r for r in routes if r["traffic"] not in {"heavy", None}), routes[0])
                rule, reason = "heavy_traffic", "Heavy traffic: use the first available non-heavy alternative."
            elif reference["traffic"] is None:
                chosen = next((r for r in routes if r["traffic"] is not None), routes[0])
                rule, reason = "unknown_sensor", "Traffic is unknown: use the first observed available route."
            else:
                chosen = reference
                rule, reason = "default_route", "No heavy traffic is observed: keep the default/current route."
            if p["status"] == "ACCEPTED" or chosen["route_id"] != p["current_route"]:
                return self.select(p, chosen["route_id"], reason, rule=rule)
        return self.move()
