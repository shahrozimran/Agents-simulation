"""Serializable, validated input and action contracts."""
from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"DELIVERED", "FAILED", "TIMED_OUT"}


@dataclass
class Route:
    route_id: str
    distance_km: float
    base_travel_min: float
    cost: float
    traffic_multiplier: float = 1.0
    traffic: str = "light"
    available: bool = True
    well_lit: bool = True
    flood_risk: float = 0.0

    def validate(self):
        if not self.route_id:
            raise ValueError("A route needs an ID.")
        for key in ("distance_km", "base_travel_min", "traffic_multiplier"):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive.")
        if not math.isfinite(self.cost) or self.cost < 0:
            raise ValueError("Route cost must be finite and nonnegative.")
        if self.traffic not in {"light", "moderate", "heavy"}:
            raise ValueError("Traffic must be light, moderate, or heavy.")
        if not math.isfinite(self.flood_risk) or not 0 <= self.flood_risk <= 1:
            raise ValueError("Flood risk must be between zero and one.")


@dataclass
class Scenario:
    scenario_id: str
    name: str
    routes: list[Route]
    deadline_min: float = 35.0
    weather: str = "clear"
    weather_multiplier: float = 1.0
    urgent: bool = False
    prep_min: float = 4.0
    handling_min: float = 1.0
    dropoff_min: float = 2.0
    seed: int = 42
    noise: bool = False
    max_time_min: float = 120.0
    events: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=lambda: {
        "time_of_day": "day", "food_type": "standard",
        "customer_preference": "balanced", "restaurant_backlog_min": 0.0,
    })

    def validate(self):
        if not self.scenario_id or not self.name:
            raise ValueError("Scenario needs an ID and name.")
        ids = [r.route_id for r in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("Route IDs must be unique.")
        for route in self.routes:
            route.validate()
        for key in ("deadline_min", "weather_multiplier", "max_time_min"):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive.")
        for key in ("prep_min", "handling_min", "dropoff_min"):
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be finite and nonnegative.")
        if self.weather not in {"clear", "rain"}:
            raise ValueError("Weather must be clear or rain.")
        if self.context.get("time_of_day", "day") not in {"day", "night"}:
            raise ValueError("Time of day must be day or night.")
        if self.context.get("food_type", "standard") not in {"standard", "hot", "frozen"}:
            raise ValueError("Food type must be standard, hot, or frozen.")
        if self.context.get("customer_preference", "balanced") not in {"balanced", "economy", "fastest"}:
            raise ValueError("Customer preference must be balanced, economy, or fastest.")
        backlog = self.context.get("restaurant_backlog_min", 0)
        if not math.isfinite(backlog) or backlog < 0:
            raise ValueError("Restaurant backlog must be nonnegative and finite.")
        for event in self.events:
            if not math.isfinite(event["time"]) or event["time"] < 0:
                raise ValueError("Event time must be nonnegative and finite.")
            kind = event["kind"]
            if kind not in {"traffic", "close", "open", "hide", "reveal", "weather"}:
                raise ValueError(f"Unknown event kind: {kind}")
            if kind != "weather" and event.get("route_id") not in ids:
                raise ValueError("Event refers to an unknown route.")
            if kind in {"traffic", "weather"}:
                if not math.isfinite(event.get("multiplier", 0)) or event["multiplier"] <= 0:
                    raise ValueError("Event multiplier must be finite and positive.")
                label = event.get("label")
                if label not in ({"clear", "rain"} if kind == "weather" else {"light", "moderate", "heavy"}):
                    raise ValueError("Event has an invalid condition label.")
        return self

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["routes"] = [Route(**r) for r in data["routes"]]
        return cls(**data).validate()

    def clone(self):
        return self.from_dict(self.to_dict())


@dataclass
class Action:
    kind: str
    route_id: str | None = None


@dataclass
class Decision:
    action: Action
    reason: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def load_scenarios(path=None):
    path = Path(path) if path else ROOT / "data" / "scenarios.json"
    return [Scenario.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))]
