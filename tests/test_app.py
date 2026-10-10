import pytest
from streamlit.testing.v1 import AppTest
from agents import AGENTS
from core.models import ROOT


@pytest.fixture(autouse=True)
def isolate_generated_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("FOOD_AGENT_OUTPUT_DIR", str(tmp_path / "outputs"))


def button(app, label):
    return next(b for b in app.button if b.label == label)


def select(app, label):
    return next(s for s in app.selectbox if s.label == label)


@pytest.mark.parametrize("agent_name", list(AGENTS))
def test_agent_dashboard_step_complete_reset_and_replay(tmp_path, monkeypatch, agent_name):
    monkeypatch.setenv("FOOD_AGENT_DB", str(tmp_path / "ui.db"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    select(app, "Agent architecture").select(agent_name).run()
    assert not app.exception
    button(app, "Step").click().run()
    assert not app.exception
    run = app.session_state[f"run_{agent_name}"]
    assert len(run.trace) == 1
    assert run.env.status == "ACCEPTED"
    button(app, "Run to completion").click().run()
    assert not app.exception
    assert run.env.status == "DELIVERED"
    count = len(run.trace)
    next(s for s in app.slider if s.label == "Replay recorded step").set_value(1).run()
    assert len(run.trace) == count
    button(app, "Reset delivery").click().run()
    assert not app.exception
    assert app.session_state[f"run_{agent_name}"].env.status == "PLACED"
    assert len(app.session_state[f"run_{agent_name}"].trace) == 0


def test_comparison_and_history_dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("FOOD_AGENT_DB", str(tmp_path / "ui.db"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.radio[0].set_value("Comparison").run()
    button(app, "Run 21 deliveries").click().run()
    assert not app.exception
    assert len(app.session_state["comparison"]) == 21
    app.radio[0].set_value("History").run()
    assert not app.exception
    assert select(app, "Open saved delivery").options


def test_learning_dashboard_train_evaluate_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("FOOD_AGENT_DB", str(tmp_path / "ui.db"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.radio[0].set_value("Learning Lab").run()
    next(s for s in app.slider if s.label == "Training samples per route and context").set_value(1).run()
    button(app, "Train and save policy").click().run()
    assert not app.exception
    button(app, "Evaluate frozen policy").click().run()
    assert not app.exception
    assert len(app.session_state["evaluation"]) == 60
    button(app, "Reset learning").click().run()
    assert not app.exception
    assert not app.info or any("No saved policy" in i.value for i in app.info)


def test_custom_scenario_context_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("FOOD_AGENT_DB", str(tmp_path / "ui.db"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    select(app, "Agent architecture").select("Contextual").run()
    select(app, "Delivery situation").select("Custom scenario").run()
    select(app, "Time of day").select("night")
    button(app, "Apply edited scenario").click().run()
    assert not app.exception
    button(app, "Run to completion").click().run()
    assert not app.exception
    run = app.session_state["run_Contextual"]
    assert run.scenario.context["time_of_day"] == "night"
    assert run.env.current_route == "C"
