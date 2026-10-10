"""A discrete event delivery world. Agents never access its hidden truth."""
from dataclasses import asdict
import math
import random

from core.models import Action, Scenario, TERMINAL


class DeliveryEnvironment:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario.clone()
        self.routes = {r.route_id: r for r in self.scenario.routes}
        self.time = 0.0
        self.status = "PLACED"
        self.current_route = None
        self.progress = 0.0
        self.distance = self.cost = 0.0
        self.reroutes = self.waits = 0
        self.failure_reason = ""
        self.hidden = set()
        self.events = sorted(self.scenario.events, key=lambda e: e["time"])
        self.event_index = 0
        self.event_log = []
        # Pre-generate one factor per route so action counts do not alter randomness.
        self.noise_factors = {
            key: random.Random(f"{scenario.seed}:{key}").uniform(0.88, 1.12)
            if scenario.noise else 1.0 for key in self.routes
        }
        self._events()

    @property
    def terminal(self):
        return self.status in TERMINAL

    @property
    def at_junction(self):
        return abs(self.progress * 4 - round(self.progress * 4)) < 1e-7

    def _events(self):
        while self.event_index < len(self.events) and self.events[self.event_index]["time"] <= self.time + 1e-8:
            event = self.events[self.event_index]
            self.event_index += 1
            kind, key = event["kind"], event.get("route_id")
            if kind == "traffic":
                self.routes[key].traffic = event["label"]
                self.routes[key].traffic_multiplier = event["multiplier"]
            elif kind in {"close", "open"}:
                self.routes[key].available = kind == "open"
            elif kind == "hide":
                self.hidden.add(key)
            elif kind == "reveal":
                self.hidden.discard(key)
            elif kind == "weather":
                self.scenario.weather = event["label"]
                self.scenario.weather_multiplier = event["multiplier"]
            self.event_log.append(dict(event))

    def percept(self):
        routes = []
        for key, route in self.routes.items():
            item = asdict(route)
            if key in self.hidden:
                item["traffic"] = item["traffic_multiplier"] = None
            routes.append(item)
        ready_at = self.scenario.prep_min + self.scenario.context.get("restaurant_backlog_min", 0)
        return {
            "time": round(self.time, 8), "status": self.status,
            "current_route": self.current_route, "progress": round(self.progress, 8),
            "at_junction": self.at_junction, "routes": routes,
            "weather": self.scenario.weather, "weather_multiplier": self.scenario.weather_multiplier,
            "deadline": self.scenario.deadline_min, "urgent": self.scenario.urgent,
            "pickup_ready": self.time >= ready_at - 1e-8,
            "pickup_remaining": max(0, ready_at - self.time) + self.scenario.handling_min
                if self.status in {"PLACED", "ACCEPTED", "ROUTE_SELECTED"} else 0.0,
            "handling_min": self.scenario.handling_min, "dropoff_min": self.scenario.dropoff_min,
            "cost_so_far": self.cost, "distance_so_far": self.distance,
            "context": dict(self.scenario.context),
        }

    def _require(self, condition, message):
        if not condition:
            raise ValueError(message)

    def _advance(self, duration, completing=False):
        # Clamp every time-consuming action at the global time limit.
        actual = min(duration, max(0, self.scenario.max_time_min - self.time))
        self.time += actual
        self._events()
        if actual < duration - 1e-8 or (self.time >= self.scenario.max_time_min - 1e-8 and not completing):
            self.status = "TIMED_OUT"
            self.failure_reason = "Maximum simulation time reached."
        return actual

    def apply(self, action: Action):
        self._require(not self.terminal, "A terminal delivery cannot execute another action.")
        kind = action.kind
        if kind == "ACCEPT_ORDER":
            self._require(self.status == "PLACED", "Order has already been accepted.")
            self.status = "ACCEPTED"
        elif kind in {"SELECT_ROUTE", "REROUTE"}:
            self._require(action.route_id in self.routes, "Unknown route.")
            self._require(self.routes[action.route_id].available, "Route is closed.")
            if kind == "SELECT_ROUTE":
                self._require(self.status in {"ACCEPTED", "ROUTE_SELECTED"}, "Select a route before pickup.")
                self.status = "ROUTE_SELECTED"
            else:
                self._require(self.status in {"PICKED_UP", "IN_TRANSIT"} and self.at_junction,
                              "Rerouting requires a road junction and completed pickup.")
                self._require(action.route_id != self.current_route, "Already using that route.")
                self.reroutes += 1
                self._advance(1.0)
            self.current_route = action.route_id
        elif kind == "WAIT":
            duration = 1.0
            if self.status == "ROUTE_SELECTED" and not self.percept()["pickup_ready"]:
                ready_at = self.scenario.prep_min + self.scenario.context.get("restaurant_backlog_min", 0)
                duration = min(duration, ready_at - self.time)
            if self.event_index < len(self.events):
                duration = min(duration, self.events[self.event_index]["time"] - self.time)
            self._advance(duration)
            self.waits += 1
        elif kind == "PICK_UP":
            self._require(self.status == "ROUTE_SELECTED" and self.percept()["pickup_ready"],
                          "Pickup requires a route and ready food.")
            self._advance(self.scenario.handling_min)
            if not self.terminal:
                self.status = "PICKED_UP"
        elif kind == "MOVE":
            self._require(self.status in {"PICKED_UP", "IN_TRANSIT"}, "Pick up food before moving.")
            route = self.routes[self.current_route]
            self._require(route.available, "Closed route; reroute at a junction or report failure.")
            travel = route.base_travel_min * route.traffic_multiplier * self.scenario.weather_multiplier * self.noise_factors[route.route_id]
            next_junction = min(1.0, (math.floor(self.progress * 4 + 1e-7) + 1) / 4)
            duration = min(1.0, (next_junction - self.progress) * travel)
            if self.event_index < len(self.events):
                duration = min(duration, self.events[self.event_index]["time"] - self.time)
            self.status = "IN_TRANSIT"
            actual = self._advance(max(duration, 0.0))
            portion = actual / travel
            self.progress = min(1.0, self.progress + portion)
            self.distance += portion * route.distance_km
            self.cost += portion * route.cost
            if self.progress >= 1 - 1e-8 and not self.terminal:
                self.progress = 1.0
                self.status = "ARRIVED"
        elif kind == "CONFIRM_DELIVERY":
            self._require(self.status == "ARRIVED", "Confirmation requires arrival with the food.")
            self._advance(self.scenario.dropoff_min, completing=True)
            if not self.terminal:
                self.status = "DELIVERED"
        elif kind == "REPORT_FAILURE":
            self.status = "FAILED"
            self.failure_reason = "Agent reported that no valid delivery action is available."
        else:
            raise ValueError(f"Unknown action: {kind}")
        self._events()

    def outcome(self):
        return {
            "status": self.status, "delivered": self.status == "DELIVERED",
            "time_min": round(self.time, 4), "cost": round(self.cost, 4),
            "distance_km": round(self.distance, 4), "route": self.current_route,
            "deadline_met": self.status == "DELIVERED" and self.time <= self.scenario.deadline_min + 1e-8,
            "lateness_min": round(max(0, self.time - self.scenario.deadline_min), 4),
            "reroutes": self.reroutes, "waits": self.waits, "failure_reason": self.failure_reason,
        }
