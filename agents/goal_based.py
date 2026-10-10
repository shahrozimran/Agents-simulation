from agents.base import BaseAgent
from core.metrics import predicted_total


class GoalBasedAgent(BaseAgent):
    name = "Goal-Based"

    def decide(self, p):
        common = self.lifecycle(p)
        if common:
            return common
        failure = self.guard(p)
        if failure:
            return failure
        if p["status"] == "ACCEPTED" or p["at_junction"]:
            plans = []
            for route in p["routes"]:
                if route["available"]:
                    eta = predicted_total(p, route, p["current_route"] not in {None, route["route_id"]})
                    plans.append({"route_id": route["route_id"], "completion_min": eta,
                                  "feasible": eta <= p["deadline"] + 1e-8,
                                  "plan": ["accept", "choose route", "pick up", f"traverse {route['route_id']}", "confirm"]})
            feasible = [plan for plan in plans if plan["feasible"]]
            current = next((plan for plan in plans if plan["route_id"] == p["current_route"]), None)
            if p["status"] != "ACCEPTED" and current and (current["feasible"] or not feasible):
                return self.decision("MOVE", "Continue the current plan; no feasible replacement is needed.",
                                     goal="delivered within deadline", candidates=plans, goal_feasible=bool(feasible))
            chosen = min(feasible, key=lambda plan: plan["route_id"]) if feasible else min(plans, key=lambda plan: (plan["completion_min"], plan["route_id"]))
            reason = "Choose a deadline-feasible plan using the fixed route-ID tie-break." if feasible else "Deadline goal is infeasible; attempt the fastest available fallback."
            if chosen["route_id"] == p["current_route"]:
                return self.decision("MOVE", reason, candidates=plans, goal_feasible=False)
            return self.select(p, chosen["route_id"], reason, goal="delivered within deadline",
                               candidates=plans, goal_feasible=bool(feasible), selected_plan=chosen["plan"])
        return self.move()
