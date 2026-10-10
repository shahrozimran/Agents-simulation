"""Shared prediction and preference functions; no access to simulator truth."""
def predicted_total(percept, route, switching=False):
    travel = route["base_travel_min"] * (route.get("traffic_multiplier") or 1.0) * percept["weather_multiplier"]
    return percept["time"] + percept["pickup_remaining"] + travel * (1 - percept["progress"]) + percept["dropoff_min"] + (1.0 if switching else 0.0)


def utility_components(time, cost, distance, traffic, deadline, urgent=False, weights=None):
    weights = weights or ([0.60, 0.15, 0.10, 0.15] if urgent else [0.45, 0.25, 0.15, 0.15])
    terms = dict(zip(["time_penalty", "cost_penalty", "distance_penalty", "congestion_penalty"],
                     [weights[0] * time / 45, weights[1] * cost / 200,
                      weights[2] * distance / 10, weights[3] * traffic / 3]))
    terms["late_penalty"] = 2 * max(0, time - deadline) / 45
    return {**terms, "utility": -sum(terms.values())}


def route_scores(percept, weights=None):
    rows = []
    for route in percept["routes"]:
        if not route["available"]:
            continue
        switching = percept["current_route"] is not None and route["route_id"] != percept["current_route"] and percept["status"] in {"PICKED_UP", "IN_TRANSIT"}
        eta = predicted_total(percept, route, switching)
        cost = percept["cost_so_far"] + route["cost"] * (1 - percept["progress"])
        distance = percept["distance_so_far"] + route["distance_km"] * (1 - percept["progress"])
        rows.append({"route_id": route["route_id"], "eta_min": round(eta, 5), "cost": cost,
                     "distance_km": distance, "traffic": route["traffic"],
                     **utility_components(eta, cost, distance, route.get("traffic_multiplier") or 1,
                                          percept["deadline"], percept["urgent"], weights)})
    return rows


def reward_for(outcome, scenario, route_id):
    if not outcome["delivered"]:
        return -5.0
    route = next(r for r in scenario.routes if r.route_id == route_id)
    return utility_components(outcome["time_min"], outcome["cost"], outcome["distance_km"],
                              route.traffic_multiplier, scenario.deadline_min, scenario.urgent)["utility"]
