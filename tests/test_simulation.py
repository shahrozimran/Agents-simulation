import pytest
from agents import AGENTS
from core.environment import DeliveryEnvironment
from core.models import Action, load_scenarios, ROOT
from core.runner import DeliveryRun, compare


@pytest.mark.parametrize("name", list(AGENTS))
@pytest.mark.parametrize("scenario", load_scenarios(), ids=lambda s: s.scenario_id)
def test_common_scenarios_complete_without_illegal_actions(name, scenario):
    run = DeliveryRun(scenario, name).complete()
    assert run.env.outcome()["delivered"]
    assert not any(event["error"] for event in run.trace)
    assert run.trace[0]["decision"]["action"]["kind"] == "ACCEPT_ORDER"
    assert run.trace[-1]["decision"]["action"]["kind"] == "CONFIRM_DELIVERY"


@pytest.mark.parametrize("scenario", load_scenarios(), ids=lambda s: s.scenario_id)
@pytest.mark.parametrize("route_id", ["A", "B", "C"])
def test_actual_static_time_matches_physics(scenario, route_id):
    env = DeliveryEnvironment(scenario)
    env.apply(Action("ACCEPT_ORDER"))
    env.apply(Action("SELECT_ROUTE", route_id))
    while not env.percept()["pickup_ready"]:
        env.apply(Action("WAIT"))
    env.apply(Action("PICK_UP"))
    while env.status != "ARRIVED":
        env.apply(Action("MOVE"))
    env.apply(Action("CONFIRM_DELIVERY"))
    route = next(r for r in scenario.routes if r.route_id == route_id)
    expected = scenario.prep_min + scenario.handling_min + route.base_travel_min * route.traffic_multiplier * scenario.weather_multiplier + scenario.dropoff_min
    assert env.time == pytest.approx(expected)
    assert env.cost == pytest.approx(route.cost)
    assert env.distance == pytest.approx(route.distance_km)


def test_action_preconditions_and_terminal_guard():
    env = DeliveryEnvironment(load_scenarios()[0])
    for action in [Action("MOVE"), Action("PICK_UP"), Action("CONFIRM_DELIVERY"), Action("SELECT_ROUTE", "A")]:
        with pytest.raises(ValueError):
            env.apply(action)
    env.apply(Action("REPORT_FAILURE"))
    with pytest.raises(ValueError):
        env.apply(Action("ACCEPT_ORDER"))


@pytest.mark.parametrize("name", list(AGENTS))
@pytest.mark.parametrize("scenario", load_scenarios(ROOT / "data" / "supplementary.json"), ids=lambda s: s.scenario_id)
def test_supplementary_scenarios_reach_valid_terminal_state(name, scenario):
    run = DeliveryRun(scenario, name).complete()
    assert run.env.terminal
    assert not any(event["error"] for event in run.trace)
    if scenario.scenario_id == "X6":
        assert run.env.status == "FAILED"


def test_junction_recovery_preserves_sunk_distance_and_cost():
    scenario = load_scenarios(ROOT / "data" / "supplementary.json")[1]
    run = DeliveryRun(scenario, "Hierarchical").complete()
    assert run.env.status == "DELIVERED"
    assert run.env.reroutes == 1
    assert run.env.cost == pytest.approx(25 + 90)
    assert run.env.distance == pytest.approx(1.25 + 4.5)
    assert run.env.time == pytest.approx(7.5 + 1 + 9 + 2)
    recovery = next(e for e in run.trace if e["decision"]["action"]["kind"] == "REROUTE")
    assert recovery["decision"]["evidence"]["task_tree"]["recovery"] == "Find alternative route"


def test_timeout_and_exact_limit_completion():
    s = load_scenarios()[0]
    s.max_time_min = 10
    run = DeliveryRun(s, "Simple Reflex").complete()
    assert run.env.status == "TIMED_OUT"
    assert run.env.time == pytest.approx(10)
    s.max_time_min = 17
    assert DeliveryRun(s, "Simple Reflex").complete().env.status == "DELIVERED"


def test_fractional_preparation_ends_wait_at_ready_time():
    s = load_scenarios()[0]
    s.prep_min = 4.3
    run = DeliveryRun(s, "Simple Reflex").complete()
    assert run.env.time == pytest.approx(17.3)


def test_comparison_has_independent_states_and_reproducible_noise():
    s = load_scenarios()[0]
    s.noise = True
    runs = compare([s])
    assert len(runs) == 7
    assert len({id(r.env) for r in runs}) == 7
    assert all(r.env.noise_factors == runs[0].env.noise_factors for r in runs)
    before = runs[1].env.routes["A"].cost
    runs[0].env.routes["A"].cost = 999
    assert runs[1].env.routes["A"].cost == before
