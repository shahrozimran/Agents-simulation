"""Offline comparison, training and individual agent demonstrations."""
import argparse
import csv
import json
from pathlib import Path

from agents import AGENTS, SLUGS
from agents.learning import LearningAgent
from core.models import ROOT, load_scenarios
from core.runner import DeliveryRun, compare
from core.storage import Store
from training import train, evaluate


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def export_runs(runs, output):
    write_csv(output, [run.result_row() for run in runs])
    traces = Path(output).parent / "traces" / Path(output).stem
    traces.mkdir(parents=True, exist_ok=True)
    for run in runs:
        path = traces / f"{run.scenario.scenario_id}_{SLUGS[run.agent_name]}.json"
        path.write_text(json.dumps(run.export(), indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("compare", help="Run seven independent agents on all selected scenarios.")
    p.add_argument("--scenarios", default=str(ROOT / "data" / "scenarios.json"))
    p.add_argument("--output", default=str(ROOT / "outputs" / "results.csv"))
    p.add_argument("--cold-start", action="store_true")
    p = sub.add_parser("train", help="Train and persist route values, then evaluate held-out seeds.")
    p.add_argument("--samples", type=int, default=20)
    p.add_argument("--continue-learning", action="store_true")
    p = sub.add_parser("run", help="Print one agent's complete decision trace.")
    p.add_argument("--agent", choices=list(AGENTS), required=True)
    p.add_argument("--scenario", default="S3")
    p.add_argument("--scenarios", default=str(ROOT / "data" / "scenarios.json"))
    sub.add_parser("reset-learning", help="Clear saved policies while retaining delivery history.")
    args = parser.parse_args()
    store = Store()
    if args.command == "train":
        scenarios = load_scenarios()
        policy, records = train(scenarios, args.samples, store.latest_policy() if args.continue_learning else None)
        store.save_policy(policy, records)
        write_csv(ROOT / "outputs" / "training.csv", records)
        write_csv(ROOT / "outputs" / "learning_evaluation.csv", evaluate(scenarios, policy))
        (ROOT / "outputs" / "trained_policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")
        print(f"Saved {policy['policy_version']}; {len(records)} episodes and 60 held-out evaluations.")
    elif args.command == "compare":
        runs = compare(load_scenarios(args.scenarios), None if args.cold_start else store.latest_policy())
        for run in runs:
            store.save_run(run)
            row = run.result_row()
            print(f"{row['scenario']} | {row['agent']:<19} | route {row['route']} | {row['time_min']:6.2f} min | on time: {row['deadline_met']}")
        export_runs(runs, args.output)
        print(f"Saved {len(runs)} runs to {args.output}")
    elif args.command == "run":
        scenario = next((s for s in load_scenarios(args.scenarios) if s.scenario_id == args.scenario), None)
        if scenario is None:
            parser.error("Unknown scenario ID.")
        agent = LearningAgent(store.latest_policy()) if args.agent == "Learning" else None
        run = DeliveryRun(scenario, args.agent, agent).complete()
        store.save_run(run)
        for step in run.trace:
            d = step["decision"]
            print(f"{step['step']:3} | t={step['percept']['time']:6.2f} | {d['action']['kind']:<18} | {d['reason']}")
        print(json.dumps(run.result_row(), indent=2))
    else:
        store.reset_learning()
        print("Saved learning cleared. Delivery history retained.")


if __name__ == "__main__":
    main()
