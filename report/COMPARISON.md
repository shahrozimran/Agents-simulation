# Seven-agent comparison and conclusion

This report describes measured local simulator runs, not real deliveries. Every agent ran independently on the same three synthetic fixtures. Architecture explanations are available in README.md and in each exported JSON trace.

## Common scenario results with the saved learning policy

| Agent | Scenario | Route | Time (min) | Cost | On time |
|---|---|---|---|---|---|
| Simple Reflex | S1 | A | 17.00 | 100 | True |
| Model-Based Reflex | S1 | A | 17.00 | 100 | True |
| Goal-Based | S1 | A | 17.00 | 100 | True |
| Utility-Based | S1 | A | 17.00 | 100 | True |
| Learning | S1 | A | 17.00 | 100 | True |
| Hierarchical | S1 | A | 17.00 | 100 | True |
| Contextual | S1 | A | 17.00 | 100 | True |
| Simple Reflex | S2 | B | 24.60 | 150 | True |
| Model-Based Reflex | S2 | B | 24.60 | 150 | True |
| Goal-Based | S2 | A | 29.00 | 100 | True |
| Utility-Based | S2 | C | 22.60 | 120 | True |
| Learning | S2 | C | 22.60 | 120 | True |
| Hierarchical | S2 | C | 22.60 | 120 | True |
| Contextual | S2 | C | 22.60 | 120 | True |
| Simple Reflex | S3 | B | 29.00 | 150 | False |
| Model-Based Reflex | S3 | B | 29.00 | 150 | False |
| Goal-Based | S3 | C | 26.50 | 120 | True |
| Utility-Based | S3 | C | 26.50 | 120 | True |
| Learning | S3 | C | 26.50 | 120 | True |
| Hierarchical | S3 | C | 26.50 | 120 | True |
| Contextual | S3 | C | 26.50 | 120 | True |

## Cold-start comparison

| Agent | Scenario | Route | Time (min) | Cost | On time |
|---|---|---|---|---|---|
| Simple Reflex | S1 | A | 17.00 | 100 | True |
| Model-Based Reflex | S1 | A | 17.00 | 100 | True |
| Goal-Based | S1 | A | 17.00 | 100 | True |
| Utility-Based | S1 | A | 17.00 | 100 | True |
| Learning | S1 | A | 17.00 | 100 | True |
| Hierarchical | S1 | A | 17.00 | 100 | True |
| Contextual | S1 | A | 17.00 | 100 | True |
| Simple Reflex | S2 | B | 24.60 | 150 | True |
| Model-Based Reflex | S2 | B | 24.60 | 150 | True |
| Goal-Based | S2 | A | 29.00 | 100 | True |
| Utility-Based | S2 | C | 22.60 | 120 | True |
| Learning | S2 | A | 29.00 | 100 | True |
| Hierarchical | S2 | C | 22.60 | 120 | True |
| Contextual | S2 | C | 22.60 | 120 | True |
| Simple Reflex | S3 | B | 29.00 | 150 | False |
| Model-Based Reflex | S3 | B | 29.00 | 150 | False |
| Goal-Based | S3 | C | 26.50 | 120 | True |
| Utility-Based | S3 | C | 26.50 | 120 | True |
| Learning | S3 | A | 34.50 | 100 | False |
| Hierarchical | S3 | C | 26.50 | 120 | True |
| Contextual | S3 | C | 26.50 | 120 | True |

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

Training used 180 deliveries with seeded route variation and balanced route/context coverage. Held-out evaluation used 60 deliveries across separate seeds, with exploration and policy updates disabled.

| Policy | Deliveries | Deadline success | Mean time (min) | Time sample SD | Mean reward |
|---|---:|---:|---:|---:|---:|
| Cold start | 30 | 66.7% | 27.053 | 7.681 | -0.6750 |
| Trained | 30 | 90.0% | 22.061 | 4.080 | -0.5071 |


Variation combines different scenarios and route-specific travel noise; the SD is not a confidence interval. Training rewards fluctuate because exploration deliberately includes poor routes. Held-out performance is the evidence used to assess the trained policy, and applies only to this simulator/configuration.

## Conclusion

For this assignment's simultaneous time/cost/distance preferences, Utility-Based is a suitable primary architecture: its tradeoffs are explicit, adjustable and easy to inspect. Goal-Based is useful when deadline feasibility is the main criterion, while Contextual expresses situation-specific eligibility. Hierarchical makes the complete workflow and dependencies clear. Learning adapts route preferences using experience, at the cost of training and careful separate evaluation.

These seven alternatives demonstrate different architectures. This is not a multi-agent system and no architecture is claimed to be universally superior from three fixtures. A practical later system could combine planning, utility, context and learning, but that combination is outside the assignment comparison.

## Validation and reproduction

100 passed in 19.08s

Automated checks cover all 21 common runs, all 42 supplementary architecture/scenario combinations, exact travel calculations, illegal actions, timeouts, state isolation, memory expiry, feasibility, utility tradeoffs, contextual adaptation, hierarchical recovery, learning update/save/load, and dashboard interactions. UI tests use isolated database/output paths.

Reproduce from the project folder:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe cli.py train --samples 20
.\.venv\Scripts\python.exe cli.py compare --cold-start --output outputs/cold_start_results.csv
.\.venv\Scripts\python.exe cli.py compare
.\.venv\Scripts\python.exe scripts/build_report.py
```

Traces are in outputs/traces/results and outputs/traces/cold_start_results. Architecture diagrams are in diagrams/. Screenshots are in outputs/screenshots/. Each diagram is available as SVG and editable Mermaid source. The original assignment PDF remains unchanged.
