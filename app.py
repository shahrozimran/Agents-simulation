"""Interactive laboratory for seven independent food-delivery architectures."""
from copy import deepcopy
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st

from agents import AGENTS, DESCRIPTIONS, SLUGS
from agents.learning import LearningAgent
from agents.utility_based import UtilityBasedAgent
from core.models import ROOT, Scenario, load_scenarios
from core.runner import DeliveryRun, compare
from core.storage import Store
from cli import export_runs, write_csv
from training import train, evaluate

OUTPUT_DIR = Path(os.environ.get("FOOD_AGENT_OUTPUT_DIR") or ROOT / "outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Delivery Agent Lab", page_icon="🚲", layout="wide")
st.markdown("""<style>
.block-container {max-width:1350px; padding-top:3.8rem;}
h1,h2,h3 {letter-spacing:-.03em;}
[data-testid="stMetric"] {background:white; padding:16px 20px; border:1px solid #dce9df; border-radius:14px;}
[data-testid="stMetricValue"] {font-size:1.35rem;}
[data-testid="stMetricValue"] > div {white-space:normal; overflow:visible; text-overflow:clip;}
.lab-tag {color:#137d70; text-transform:uppercase; font-size:12px; font-weight:700; letter-spacing:.14em;}
.lab-lead {color:#587167; font-size:17px; margin-bottom:24px;}
.route-card {background:#fff; border:1px solid #dce9df; border-radius:18px; padding:10px;}
</style>""", unsafe_allow_html=True)


def get_store():
    return Store(os.environ.get("FOOD_AGENT_DB") or None)


def route_visual(p):
    """A schematic with shared junctions; this is not a geographic map."""
    colors = ["#137D70", "#D5963E", "#687DC1", "#996AA8"]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 265" width="100%" role="img" aria-label="Delivery route progress">',
           '<rect width="480" height="265" rx="18" fill="#FFFFFF"/>',
           '<text x="30" y="30" font-family="Arial" font-size="14" fill="#587167">SCHEMATIC DELIVERY ROUTES</text>']
    for i, r in enumerate(p["routes"]):
        y = 65 + i * 52
        c = colors[i % len(colors)] if r["available"] else "#B4BDB8"
        svg.append(f'<line x1="70" y1="{y}" x2="425" y2="{y}" stroke="{c}" stroke-width="7" stroke-linecap="round"/>')
        for j in range(5):
            svg.append(f'<circle cx="{70+88.75*j}" cy="{y}" r="5" fill="#FFFFFF" stroke="{c}" stroke-width="2"/>')
        label = escape(f"{r['route_id']} · {r['distance_km']:g} km · {r['traffic'] or 'unknown'}" + (" · closed" if not r["available"] else ""))
        svg.append(f'<text x="70" y="{y-14}" font-family="Arial" font-size="15" fill="#19372E">{label}</text>')
        if p["current_route"] == r["route_id"]:
            svg.append(f'<circle cx="{70+355*p["progress"]}" cy="{y}" r="11" fill="#19372E" stroke="#FFFFFF" stroke-width="3"/>')
    svg += ['<text x="30" y="240" font-family="Arial" font-size="13" fill="#587167">Restaurant</text>',
            '<text x="365" y="240" font-family="Arial" font-size="13" fill="#587167">Customer</text></svg>']
    st.markdown('<div class="route-card">' + "".join(svg) + '</div>', unsafe_allow_html=True)


def show_evidence(event):
    decision = event["decision"]
    st.write(f"**{decision['action']['kind'].replace('_', ' ')}**" +
             (f" · Route {decision['action']['route_id']}" if decision["action"]["route_id"] else ""))
    st.write(decision["reason"])
    evidence = decision["evidence"]
    if "scores" in evidence:
        st.dataframe(pd.DataFrame(evidence["scores"]).round(4), hide_index=True, width="stretch")
    if "candidates" in evidence:
        rows = deepcopy(evidence["candidates"])
        for row in rows:
            row["plan"] = " → ".join(row["plan"])
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Goal feasible: " + str(evidence["goal_feasible"]))
    if "task_tree" in evidence:
        tree = evidence["task_tree"]
        st.write("**Active subgoal:** " + tree["active"])
        if tree["recovery"]:
            st.warning("Recovery subtask: " + tree["recovery"])
        st.write(" → ".join(("✓ " if task in tree["completed"] else "") + task for task in tree["tasks"]))
    if "filters" in evidence:
        for item in evidence["filters"]:
            st.write("• " + item)
    if "belief_updates" in evidence:
        for item in evidence["belief_updates"]:
            st.write("• " + item)
    if "values" in evidence and evidence["values"]:
        st.dataframe(pd.DataFrame([{"route": key, **row} for key, row in evidence["values"].items()]), hide_index=True)
    with st.expander("Complete decision evidence"):
        st.json(evidence)


def show_trace(payload, key):
    trace = payload["trace"]
    if not trace:
        st.info("Use Step or Run to completion to generate the first decision.")
        return
    rows = [{"Step": e["step"], "Minute": e["percept"]["time"], "Before": e["percept"]["status"],
             "Action": e["decision"]["action"]["kind"], "Route": e["decision"]["action"]["route_id"],
             "After": e["after"]["status"], "Reason": e["decision"]["reason"]} for e in trace]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=320)
    index = st.slider("Replay recorded step", 1, max(2, len(trace)), len(trace), key=f"replay_{key}") - 1
    index = min(index, len(trace) - 1)
    event = trace[index]
    left, right = st.columns([1.1, 1])
    with left:
        route_visual(event["after"])
        st.caption(f"Replay minute {event['after']['time']:.2f} · {event['after']['status']} · recorded data only")
    with right:
        show_evidence(event)
    with st.expander("Observation and internal-state transition"):
        a, b = st.columns(2)
        a.json({"percept": event["percept"], "state_before": event["state_before"]})
        b.json({"state_after": event["state_after"], "environment_events": event["environment_events"]})
    st.download_button("Download complete trace JSON", json.dumps(payload, indent=2),
                       f"{payload['scenario']['scenario_id']}_{SLUGS[payload['agent']]}.json", "application/json", key=f"json_{key}")


def configure_scenario(agent_name):
    choices = load_scenarios() + load_scenarios(ROOT / "data" / "supplementary.json")
    labels = [f"{s.scenario_id} · {s.name}" for s in choices] + ["Custom scenario"]
    selected = st.selectbox("Delivery situation", labels, key=f"scenario_{agent_name}")
    is_custom = selected == "Custom scenario"
    base = choices[0] if is_custom else choices[labels.index(selected)]
    with st.expander("Edit inputs and context", expanded=is_custom):
        with st.form(f"scenario_form_{agent_name}_{base.scenario_id}"):
            a, b, c = st.columns(3)
            deadline = a.number_input("Deadline (minutes)", min_value=1.0, value=float(base.deadline_min), step=1.0)
            weather = b.selectbox("Weather", ["clear", "rain"], index=int(base.weather == "rain"))
            urgent = c.checkbox("Urgent delivery", value=base.urgent)
            prep = a.number_input("Restaurant preparation (minutes)", min_value=0.0, value=float(base.prep_min))
            noise = b.checkbox("Seeded travel variation", value=base.noise)
            seed = c.number_input("Simulation seed", min_value=0, value=int(base.seed), step=1)
            day = a.selectbox("Time of day", ["day", "night"], index=int(base.context.get("time_of_day") == "night"))
            food = b.selectbox("Food type", ["standard", "hot", "frozen"], index=["standard", "hot", "frozen"].index(base.context.get("food_type", "standard")))
            preference = c.selectbox("Customer preference", ["balanced", "economy", "fastest"], index=["balanced", "economy", "fastest"].index(base.context.get("customer_preference", "balanced")))
            backlog = a.number_input("Additional restaurant backlog (minutes)", min_value=0.0, value=float(base.context.get("restaurant_backlog_min", 0)))
            st.caption("Edit route distance, base travel, cost, traffic, availability, lighting and flood risk. Traffic labels: light / moderate / heavy.")
            routes = st.data_editor(pd.DataFrame([r.__dict__ for r in base.routes]), hide_index=True,
                                    disabled=["route_id"], width="stretch", key=f"routes_{agent_name}_{base.scenario_id}")
            applied = st.form_submit_button("Apply edited scenario", type="primary")
        custom_key = f"custom_{agent_name}_{selected}"
        if applied:
            data = base.to_dict()
            data.update(scenario_id=f"CUSTOM-{base.scenario_id}", name="Custom delivery situation",
                        deadline_min=deadline, weather=weather, weather_multiplier=1.25 if weather == "rain" else 1.0,
                        urgent=urgent, prep_min=prep, noise=noise, seed=int(seed), routes=routes.to_dict("records"),
                        context={"time_of_day": day, "food_type": food, "customer_preference": preference,
                                 "restaurant_backlog_min": backlog})
            try:
                st.session_state[custom_key] = Scenario.from_dict(data)
                st.success("Inputs applied. A fresh run will use this configuration.")
            except (ValueError, TypeError) as exc:
                st.error(f"Please correct the input: {exc}")
        scenario = st.session_state.get(custom_key, base).clone()
        if custom_key in st.session_state and st.button("Restore original preset", key=f"restore_{custom_key}"):
            del st.session_state[custom_key]
            st.rerun()
        st.download_button("Download scenario JSON", json.dumps(scenario.to_dict(), indent=2), "scenario.json", "application/json", key=f"scenario_download_{agent_name}")
    st.caption(f"{scenario.scenario_id} · {scenario.weather} · deadline {scenario.deadline_min:g} min · {'urgent' if scenario.urgent else 'standard'} · food preparation {scenario.prep_min:g} min")
    return scenario


def agent_lab(store, name):
    st.markdown('<div class="lab-tag">Seven architectures · one delivery world</div>', unsafe_allow_html=True)
    st.title(name + " Agent")
    st.markdown('<div class="lab-lead">' + DESCRIPTIONS[name] + '</div>', unsafe_allow_html=True)
    scenario = configure_scenario(name)
    policy = store.latest_policy() if name == "Learning" else None
    weights = None
    if name == "Utility-Based":
        with st.expander("Utility preferences"):
            st.caption("Weights are normalized to sum to one. Defaults adapt to urgency.")
            if st.checkbox("Use custom utility weights", key="custom_utility"):
                cols = st.columns(4)
                raw = [cols[i].slider(label, 0.0, 1.0, value, .05) for i, (label, value) in enumerate(zip(["Time", "Cost", "Distance", "Congestion"], [.45, .25, .15, .15]))]
                if sum(raw) == 0:
                    st.error("At least one utility weight must be positive.")
                    return
                weights = [w / sum(raw) for w in raw]
                st.write(dict(zip(["Time", "Cost", "Distance", "Congestion"], weights)))
    if name == "Learning":
        st.info("Frozen evaluation · " + (policy["policy_version"] if policy else "cold-start policy; visit Learning Lab to train"))
    signature = json.dumps({"scenario": scenario.to_dict(), "policy": policy, "weights": weights}, sort_keys=True)
    run_key = f"run_{name}"
    signature_key = f"signature_{name}"

    def fresh():
        agent = LearningAgent(policy=policy) if name == "Learning" else UtilityBasedAgent(weights) if name == "Utility-Based" else None
        return DeliveryRun(scenario, name, agent)

    if st.session_state.get(signature_key) != signature or run_key not in st.session_state:
        st.session_state[run_key], st.session_state[signature_key] = fresh(), signature
    run = st.session_state[run_key]
    a, b, c = st.columns([2, 1, 1])
    if a.button("Run to completion", type="primary", disabled=run.env.terminal, width="stretch"):
        run.complete()
        store.save_run(run)
    if b.button("Step", disabled=run.env.terminal, width="stretch"):
        run.step()
        store.save_run(run)
    if c.button("Reset delivery", width="stretch"):
        st.session_state[run_key] = fresh()
        st.rerun()
    outcome = run.env.outcome()
    cols = st.columns(4)
    cols[0].metric("Elapsed", f"{outcome['time_min']:.2f} min")
    cols[1].metric("Travel cost", f"{outcome['cost']:.0f} units")
    cols[2].metric("Distance traveled", f"{outcome['distance_km']:.2f} km")
    cols[3].metric("Delivery status", outcome["status"].replace("_", " "))
    if run.env.terminal:
        if outcome["deadline_met"]:
            st.success("Delivered within the deadline. The complete workflow is recorded below.")
        elif outcome["delivered"]:
            st.warning(f"Delivered {outcome['lateness_min']:.2f} minutes late. Deadline goal was not achieved.")
        else:
            st.error(outcome["failure_reason"])
    live, architecture, trace = st.tabs(["Live workflow", "Architecture", "Decision trace & replay"])
    with live:
        left, right = st.columns([1.2, 1])
        with left:
            route_visual(run.env.percept())
            st.progress(run.env.progress, text=f"Travel progress · {run.env.progress:.0%}")
            st.caption("Each route shares junctions at 0%, 25%, 50%, 75%, and 100%. Rerouting adds one minute and preserves travel already completed.")
        with right:
            st.subheader("Latest decision")
            if run.trace:
                show_evidence(run.trace[-1])
            else:
                st.write("The order is ready for the agent. Run the full delivery or advance one decision at a time.")
        with st.expander("Agent memory and final state"):
            st.json(run.agent.debug())
        st.caption(f"{len(run.trace)} decisions · {outcome['waits']} waits · {outcome['reroutes']} reroutes · run {run.run_id[:10]}")
    with architecture:
        path = ROOT / "diagrams" / f"{SLUGS[name]}.svg"
        st.image(path.read_text(encoding="utf-8"), width="stretch")
        st.download_button("Download architecture SVG", path.read_bytes(), path.name, "image/svg+xml", key=f"svg_{name}")
        source = (ROOT / "diagrams" / f"{SLUGS[name]}.mmd").read_text(encoding="utf-8")
        with st.expander("Mermaid diagram source"):
            st.code(source, language="mermaid")
    with trace:
        show_trace(run.export(), run.run_id)


def comparison_lab(store):
    st.markdown('<div class="lab-tag">Common conditions · independent runs</div>', unsafe_allow_html=True)
    st.title("Compare all seven agents")
    st.write("Run the three required situations with identical route conditions for every agent. Compare the results and inspect how each decision was made.")
    noise = st.checkbox("Include seeded travel variation", key="comparison_noise")
    seed = st.number_input("Comparison seed", min_value=0, value=42, step=1, key="comparison_seed")
    cold = st.checkbox("Evaluate Learning Agent from cold start", value=False)
    if st.button("Run 21 deliveries", type="primary"):
        scenarios = load_scenarios()
        for scenario in scenarios:
            scenario.noise = noise
        runs = compare(scenarios, None if cold else store.latest_policy(), int(seed))
        for run in runs:
            store.save_run(run)
        export_runs(runs, OUTPUT_DIR / "results.csv")
        st.session_state["comparison"] = [run.export() for run in runs]
    payloads = st.session_state.get("comparison", [])
    if not payloads:
        st.info("Run the comparison to generate 21 delivery outcomes.")
        return
    df = pd.DataFrame([p["result"] for p in payloads])
    a, b, c = st.columns(3)
    a.metric("Completed deliveries", f"{int(df.delivered.sum())} / {len(df)}")
    b.metric("Deadline successes", f"{int(df.deadline_met.sum())} / {len(df)}")
    c.metric("Architectures", "7")
    st.dataframe(df.drop(columns=["run_id", "failure_reason"]).round(3), hide_index=True, width="stretch")
    times = df.pivot(index="agent", columns="scenario", values="time_min")
    st.subheader("Delivery time by situation")
    st.bar_chart(times, horizontal=True)
    st.caption("The fixtures are synthetic. Shared route choices can arise from different reasoning. The learning-policy version is recorded for reproducibility.")
    st.download_button("Download comparison CSV", df.to_csv(index=False), "results.csv", "text/csv")
    selected = st.selectbox("Inspect a complete delivery", range(len(payloads)), format_func=lambda i: f"{payloads[i]['result']['scenario']} · {payloads[i]['agent']}")
    show_trace(payloads[selected], f"comparison_{payloads[selected]['run_id']}")


def learning_lab(store):
    st.markdown('<div class="lab-tag">Feedback · persistent policy · held-out evaluation</div>', unsafe_allow_html=True)
    st.title("Learning Lab")
    st.write("Train route values from delivery feedback, save them, and compare a frozen trained policy with the cold-start policy on new seeds.")
    samples = st.slider("Training samples per route and context", 1, 40, 20)
    continuing = st.checkbox("Continue from the saved policy")
    st.caption(f"Three contexts × three routes × {samples} samples = {samples * 9} training episodes. Training includes seeded travel variation.")
    if st.button("Train and save policy", type="primary"):
        with st.spinner("Simulating deliveries and updating mean rewards..."):
            policy, records = train(load_scenarios(), samples, store.latest_policy() if continuing else None)
            store.save_policy(policy, records)
            write_csv(OUTPUT_DIR / "training.csv", records)
            (OUTPUT_DIR / "trained_policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")
            st.session_state.pop("evaluation", None)
        st.success(f"Saved {len(records)} episodes. Policy persists across restarts.")
    policy = store.latest_policy()
    if policy:
        st.write("**Saved policy:** " + policy["policy_version"])
        rows = [{"context": key, "route": r, **v} for key, routes in policy["values"].items() for r, v in routes.items()]
        st.dataframe(pd.DataFrame(rows).round(5), hide_index=True, width="stretch")
        records = store.latest_training()
        if records:
            curve = pd.DataFrame(records)[["episode", "reward"]].set_index("episode")
            curve["rolling_mean_18"] = curve.reward.rolling(18, min_periods=1).mean()
            st.line_chart(curve)
            st.caption("Balanced exploration intentionally samples all routes. The curve alone is not evidence of policy improvement; use held-out evaluation below.")
        repeats = st.slider("Held-out repetitions per scenario", 1, 30, 10)
        if st.button("Evaluate frozen policy"):
            records = evaluate(load_scenarios(), policy, repeats)
            st.session_state["evaluation"] = records
            write_csv(OUTPUT_DIR / "learning_evaluation.csv", records)
        if st.session_state.get("evaluation"):
            df = pd.DataFrame(st.session_state["evaluation"])
            summary = df.groupby("policy").agg(deliveries=("delivered", "size"), deadline_rate=("deadline_met", "mean"),
                                                mean_time=("time_min", "mean"), time_std=("time_min", "std"), mean_reward=("reward", "mean"))
            st.dataframe(summary.round(4), width="stretch")
            st.download_button("Download held-out evaluation CSV", df.to_csv(index=False), "learning_evaluation.csv", "text/csv")
        with st.expander("Reset saved learning"):
            st.caption("This clears saved policy snapshots. Delivery history remains available.")
            if st.button("Reset learning"):
                store.reset_learning()
                st.session_state.pop("evaluation", None)
                st.rerun()
    else:
        st.info("No saved policy yet. Train above to create one.")
    with st.expander("Learning algorithm and reward"):
        st.code("Q(context, route) += (actual_reward - Q(context, route)) / sample_count\nreward = -(weighted_time + weighted_cost + weighted_distance + weighted_congestion + lateness_penalty)\nfailure_reward = -5", language="python")
        st.write("Context consists of weather, overall congestion, and urgency. Training covers every available route; the agent also supports epsilon-greedy exploration. Evaluation disables exploration and updates.")


def history_lab(store):
    st.title("Delivery history")
    rows = store.list_runs()
    if not rows:
        st.info("Run or step a delivery to save its history.")
        return
    st.dataframe(pd.DataFrame(rows).drop(columns=["failure_reason"]).round(3), hide_index=True, width="stretch")
    selected = st.selectbox("Open saved delivery", rows, format_func=lambda r: f"{r['run_id'][:8]} · {r['agent']} · {r['scenario']} · {r['status']}")
    show_trace(store.get_run(selected["run_id"]), "history_" + selected["run_id"])


def guide():
    st.title("Build and demo guide")
    st.markdown((ROOT / "README.md").read_text(encoding="utf-8"))


def main():
    store = get_store()
    with st.sidebar:
        st.markdown("## 🚲 Delivery Agent Lab")
        st.caption("Agent Based Modeling · Assignment 1")
        section = st.radio("Workspace", ["Agent Lab", "Comparison", "Learning Lab", "History", "Build Guide"])
        name = st.selectbox("Agent architecture", list(AGENTS))
        st.divider()
        st.caption("7 independent agents\n\n3 shared test situations\n\nLocal simulated environment")
    try:
        if section == "Agent Lab":
            agent_lab(store, name)
        elif section == "Comparison":
            comparison_lab(store)
        elif section == "Learning Lab":
            learning_lab(store)
        elif section == "History":
            history_lab(store)
        else:
            guide()
    except (OSError, ValueError) as exc:
        st.error(f"The operation could not finish: {exc}")


if __name__ == "__main__":
    main()
