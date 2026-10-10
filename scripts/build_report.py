"""Create the comparison and conclusion from measured exported outcomes."""
import csv
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def read_csv(name):
    with (ROOT / "outputs" / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def table(rows):
    headers = ["Agent", "Scenario", "Route", "Time (min)", "Cost", "On time"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append(f"| {row['agent']} | {row['scenario']} | {row['route']} | {float(row['time_min']):.2f} | {float(row['cost']):.0f} | {row['deadline_met']} |")
    return "\n".join(lines)


def main():
    rows = read_csv("results.csv")
    cold = read_csv("cold_start_results.csv")
    evaluation = read_csv("learning_evaluation.csv")
    training = read_csv("training.csv")
    test_note = "See outputs/test_results.txt for the full automated test result."
    test_path = ROOT / "outputs" / "test_results.txt"
    if test_path.exists():
        summaries = [line.strip() for line in test_path.read_text(encoding="utf-8").splitlines() if "passed" in line]
        if summaries:
            test_note = summaries[-1]
    text = """# Seven-agent comparison and conclusion

This report describes measured local simulator runs, not real deliveries. Every agent ran independently on the same three synthetic fixtures. Architecture explanations are available in README.md and in each exported JSON trace.

## Common scenario results with the saved learning policy

""" + table(rows)
    text += "\n\n## Cold-start comparison\n\n" + table(cold)
    text += """

## Behavioral differences

- **Simple Reflex** uses current IF-THEN rules. In S2/S3 it selects B because B is the first non-heavy alternative. S3 finishes at 29 minutes against a 28-minute deadline.
- **Model-Based Reflex** matches the reflex baseline when all observations are present. Its distinctive behavior is revealed by X1, which removes an observation after it has been seen. The internal state records the retained condition and observation time; stale beliefs expire after 15 minutes.
- **Goal-Based** uses deadline feasibility. It can retain A in S2 because A satisfies the 35-minute deadline and wins its declared route-ID tie-break, even though C is faster. In S3 only C is predicted to satisfy the deadline, so it selects C. X5 explicitly reports an infeasible goal.
- **Utility-Based** ranks time, cost, distance and congestion using the displayed formula. It selects C in S2/S3 under the default weights. The custom weight controls can change a route preference when inputs contain a genuine tradeoff.
- **Learning** initially uses the declared neutral prior and route-ID tie-break. Training changes route values through actual feedback. The result table identifies the saved policy version, while the held-out comparison below evaluates against new travel-variation seeds.
- **Hierarchical** exposes accept, route, pickup, delivery and confirmation subgoals. Its ChooseRoute method selects the fastest predicted route, so it selects C in S2/S3. X3 demonstrates waiting for pickup; X2 inserts a route-recovery subtask.
- **Contextual** additionally considers nighttime lighting, food type, customer preference and rain flood risk. X4 excludes unlit A and selects the cheapest eligible route. Changing only time of day from day to night with standard inputs changes its route from A to C. Restaurant backlog increases pickup readiness time for every agent because it is part of the shared environment.

Identical routes in S1 do not imply identical architectures. Their evidence distinguishes a matched rule, updated belief, feasible plan, utility table, learned values, subgoal tree, or contextual filters.

## Learning experiment

"""
    text += f"Training used {len(training)} deliveries with seeded route variation and balanced route/context coverage. Held-out evaluation used {len(evaluation)} deliveries across separate seeds, with exploration and policy updates disabled.\n\n"
    text += "| Policy | Deliveries | Deadline success | Mean time (min) | Time sample SD | Mean reward |\n|---|---:|---:|---:|---:|---:|\n"
    for label in ["Cold start", "Trained"]:
        subset = [r for r in evaluation if r["policy"] == label]
        times = [float(r["time_min"]) for r in subset]
        rate = sum(r["deadline_met"] == "True" for r in subset) / len(subset)
        reward = statistics.mean(float(r["reward"]) for r in subset)
        text += f"| {label} | {len(subset)} | {rate:.1%} | {statistics.mean(times):.3f} | {statistics.stdev(times):.3f} | {reward:.4f} |\n"
    text += """

Variation combines different scenarios and route-specific travel noise; the SD is not a confidence interval. Training rewards fluctuate because exploration deliberately includes poor routes. Held-out performance is the evidence used to assess the trained policy, and applies only to this simulator/configuration.

## Conclusion

For this assignment's simultaneous time/cost/distance preferences, Utility-Based is a suitable primary architecture: its tradeoffs are explicit, adjustable and easy to inspect. Goal-Based is useful when deadline feasibility is the main criterion, while Contextual expresses situation-specific eligibility. Hierarchical makes the complete workflow and dependencies clear. Learning adapts route preferences using experience, at the cost of training and careful separate evaluation.

These seven alternatives demonstrate different architectures. This is not a multi-agent system and no architecture is claimed to be universally superior from three fixtures. A practical later system could combine planning, utility, context and learning, but that combination is outside the assignment comparison.

## Validation and reproduction

""" + test_note + "\n\n"
    text += r"""Automated checks cover all 21 common runs, all 42 supplementary architecture/scenario combinations, exact travel calculations, illegal actions, timeouts, state isolation, memory expiry, feasibility, utility tradeoffs, contextual adaptation, hierarchical recovery, learning update/save/load, and dashboard interactions. UI tests use isolated database/output paths.

Reproduce from the project folder:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe cli.py train --samples 20
.\.venv\Scripts\python.exe cli.py compare --cold-start --output outputs/cold_start_results.csv
.\.venv\Scripts\python.exe cli.py compare
.\.venv\Scripts\python.exe scripts/build_report.py
```

Traces are in outputs/traces/results and outputs/traces/cold_start_results. Architecture diagrams are in diagrams/. Screenshots are in outputs/screenshots/. Each diagram is available as SVG and editable Mermaid source. The original assignment PDF remains unchanged.
"""
    path = ROOT / "report" / "COMPARISON.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Wrote measured report for {len(rows)} common runs and {len(evaluation)} held-out learning evaluations.")


if __name__ == "__main__":
    main()
