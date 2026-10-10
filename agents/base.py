"""Lifecycle helpers. Decision policies remain in their own architecture modules."""
from core.models import Action, Decision
from core.metrics import predicted_total


class BaseAgent:
    name = "Base"

    def reset(self, config=None):
        pass

    def debug(self):
        return {}

    def finalize(self, percept):
        pass

    def decision(self, kind, reason, route_id=None, **evidence):
        return Decision(Action(kind, route_id), reason, evidence)

    def lifecycle(self, p):
        status = p["status"]
        if status == "PLACED":
            return self.decision("ACCEPT_ORDER", "The order is placed; accept it.", rule="accept")
        if status == "ROUTE_SELECTED":
            if not p["pickup_ready"]:
                return self.decision("WAIT", "Food is not ready; wait one minute.", rule="wait_for_food")
            return self.decision("PICK_UP", "Food is ready and a route is selected; collect it.", rule="pickup")
        if status == "ARRIVED":
            return self.decision("CONFIRM_DELIVERY", "Arrived with the food; confirm delivery.", rule="confirm")
        return None

    def select(self, p, route_id, reason, **evidence):
        kind = "SELECT_ROUTE" if p["status"] == "ACCEPTED" else "REROUTE"
        return self.decision(kind, reason, route_id, **evidence)

    def guard(self, p):
        """A shared action-validity check, not a hidden route optimizer."""
        available = [r for r in p["routes"] if r["available"]]
        if not available:
            return self.decision("REPORT_FAILURE", "All routes are unavailable.", rule="no_available_route")
        current = next((r for r in p["routes"] if r["route_id"] == p["current_route"]), None)
        if current is not None and not current["available"] and not p["at_junction"]:
            return self.decision("REPORT_FAILURE", "The current segment is closed and no junction is reachable.", rule="closure_between_junctions")
        return None

    def move(self):
        return self.decision("MOVE", "Continue along the current route to the next decision point.")

    def fastest(self, p, routes):
        return min(routes, key=lambda r: (predicted_total(p, r, p["current_route"] not in {None, r["route_id"]}), r["route_id"]))
