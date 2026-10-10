from copy import deepcopy
import pytest
from agents.learning import LearningAgent
from core.models import load_scenarios
from core.runner import DeliveryRun
from core.storage import Store
from training import train, evaluate


def test_learning_update_mean_and_exactly_once():
    a = LearningAgent(training=True)
    a.selected_context, a.selected_route = "test", "A"
    a.observe_reward(-1)
    with pytest.raises(ValueError):
        a.observe_reward(-2)
    a.reset()
    a.selected_context, a.selected_route = "test", "A"
    a.observe_reward(-3)
    assert a.values["test"]["A"] == {"count": 2, "q": -2}


def test_training_coverage_and_frozen_evaluation():
    policy, records = train(load_scenarios(), samples_per_route=3)
    assert len(records) == 27
    assert len(policy["values"]) == 3
    assert all(row["count"] == 3 for routes in policy["values"].values() for row in routes.values())
    snapshot = deepcopy(policy)
    rows = evaluate(load_scenarios(), policy, repeats=2)
    assert len(rows) == 12
    assert policy == snapshot
    agent = LearningAgent(policy=policy)
    with pytest.raises(ValueError):
        agent.observe_reward(1)


def test_policy_survives_new_store_and_run_save_is_idempotent(tmp_path):
    path = tmp_path / "history.db"
    store = Store(path)
    policy, records = train(load_scenarios(), 1)
    store.save_policy(policy, records)
    assert Store(path).latest_policy() == policy
    run = DeliveryRun(load_scenarios()[0], "Simple Reflex")
    run.step()
    store.save_run(run)
    run.complete()
    store.save_run(run)
    store.save_run(run)
    assert len(store.list_runs()) == 1
    saved = store.get_run(run.run_id)
    assert saved["result"]["status"] == "DELIVERED"
    assert len(saved["trace"]) == len(run.trace)
    con = store.connect()
    assert con.execute("SELECT count(*) FROM steps").fetchone()[0] == len(run.trace)
    con.close()
    store.reset_learning()
    assert store.latest_policy() is None
    assert len(store.list_runs()) == 1
