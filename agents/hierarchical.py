from agents.base import BaseAgent


class HierarchicalAgent(BaseAgent):
    name = "Hierarchical"
    tasks = ["Accept order", "Choose route", "Pick up food", "Deliver order", "Confirm delivery"]

    def __init__(self):
        self.reset()

    def reset(self, config=None):
        self.completed = []
        self.active = self.tasks[0]
        self.recovery = None

    def debug(self):
        return {"top_level": "Complete delivery", "tasks": self.tasks,
                "completed": list(self.completed), "active": self.active, "recovery": self.recovery}

    def finalize(self, p):
        if p["status"] == "DELIVERED":
            self.completed = list(self.tasks)
            self.active = "Complete"

    def decide(self, p):
        index = {"PLACED": 0, "ACCEPTED": 1, "ROUTE_SELECTED": 2,
                 "PICKED_UP": 3, "IN_TRANSIT": 3, "ARRIVED": 4}.get(p["status"], 0)
        self.completed = self.tasks[:index]
        self.active = self.tasks[index]
        self.recovery = None
        decision = self.lifecycle(p) or self.guard(p)
        if decision is None:
            current = next((r for r in p["routes"] if r["route_id"] == p["current_route"]), None)
            if p["status"] == "ACCEPTED" or (p["at_junction"] and current and not current["available"]):
                if current:
                    self.recovery = "Find alternative route"
                chosen = self.fastest(p, [r for r in p["routes"] if r["available"]])
                decision = self.select(p, chosen["route_id"], "Execute the active routing subtask using its fastest-route method.")
            else:
                decision = self.move()
        decision.evidence["task_tree"] = self.debug()
        return decision
