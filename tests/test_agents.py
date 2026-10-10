from copy import deepcopy
import pytest
from agents.simple_reflex import SimpleReflexAgent
from agents.model_based import ModelBasedAgent
from agents.utility_based import UtilityBasedAgent
from agents.goal_based import GoalBasedAgent
from core.environment import DeliveryEnvironment
from core.models import Action, ROOT, load_scenarios
from core.runner import DeliveryRun


def routing_percept(scenario):
    env = DeliveryEnvironment(scenario)
    env.apply(Action("ACCEPT_ORDER"))
    return env.percept()


def test_reflex_is_current_percept_only_and_does_not_mutate_input():
    p = routing_percept(load_scenarios()[1])
    original = deepcopy(p)
    agent = SimpleReflexAgent()
    d1 = agent.decide(p)
    agent.decide(routing_percept(load_scenarios()[0]))
    assert agent.decide(p).to_dict() == d1.to_dict()
    assert p == original
    assert agent.debug() == {}


def test_model_retains_observation_then_expires_and_resets():
    p = routing_percept(load_scenarios()[1])
    agent = ModelBasedAgent(stale_after=15)
    agent.decide(p)
    hidden = deepcopy(p)
    hidden["time"] = 5
    hidden["routes"][0]["traffic"] = hidden["routes"][0]["traffic_multiplier"] = None
    d = agent.decide(hidden)
    assert any("retained heavy" in update for update in d.evidence["belief_updates"])
    assert hidden["routes"][0]["traffic"] is None
    hidden["time"] = 20
    agent.decide(hidden)
    assert "A" not in agent.state["route_beliefs"]
    agent.reset()
    assert agent.state["route_beliefs"] == {}


def test_goal_urgent_feasibility_and_impossible_deadline():
    agent = GoalBasedAgent()
    p = routing_percept(load_scenarios()[2])
    d = agent.decide(p)
    assert d.action.route_id == "C"
    assert d.evidence["goal_feasible"]
    p["deadline"] = 1
    d = agent.decide(p)
    assert not d.evidence["goal_feasible"]
    assert "infeasible" in d.reason


def test_utility_winner_and_weight_change():
    scenario = load_scenarios()[1]
    scenario.routes[0].cost = 1
    p = routing_percept(scenario)
    fast = UtilityBasedAgent([1, 0, 0, 0]).decide(p)
    cheap = UtilityBasedAgent([0, 1, 0, 0]).decide(p)
    assert fast.action.route_id == "C"
    assert cheap.action.route_id == "A"
    assert max(fast.evidence["scores"], key=lambda row: row["utility"])["route_id"] == fast.action.route_id


def test_hierarchy_waits_before_pickup_and_finishes_all_tasks():
    scenario = load_scenarios(ROOT / "data" / "supplementary.json")[2]
    run = DeliveryRun(scenario, "Hierarchical").complete()
    pickup = next(e for e in run.trace if e["decision"]["action"]["kind"] == "PICK_UP")
    assert pickup["percept"]["time"] >= 12
    assert run.agent.debug()["active"] == "Complete"
    assert len(run.agent.debug()["completed"]) == 5


def test_context_changes_route_without_changing_physical_route_data():
    day = load_scenarios()[0]
    night = day.clone()
    night.context["time_of_day"] = "night"
    day_run = DeliveryRun(day, "Contextual").complete()
    night_run = DeliveryRun(night, "Contextual").complete()
    assert day_run.env.current_route == "A"
    assert night_run.env.current_route == "C"
    d = next(e["decision"] for e in night_run.trace if e["decision"]["action"]["kind"] == "SELECT_ROUTE")
    assert "A" not in d["evidence"]["eligible_routes"]


def test_contextual_economy_and_temperature_sensitivity():
    s = load_scenarios()[0]
    s.routes[1].cost = 1
    s.context.update(time_of_day="night", customer_preference="economy")
    assert DeliveryRun(s, "Contextual").complete().env.current_route == "B"
    s.context["food_type"] = "hot"
    assert DeliveryRun(s, "Contextual").complete().env.current_route == "C"


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_scenario_rejects_invalid_numeric_data(value):
    s = load_scenarios()[0]
    s.routes[0].base_travel_min = value
    with pytest.raises(ValueError):
        s.validate()
