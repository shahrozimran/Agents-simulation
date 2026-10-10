# Agents-simulation

Delivery Agent Lab

A complete local food-delivery simulation demonstrating **seven independent single-agent architectures**. Includes the Contextual Agent requested in addition to the assignment's six repeatedly named agents.

## Run the application

On this computer, dependencies are already installed in `.venv`. Open PowerShell in this folder and run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **http://localhost:8501**. Alternatively, right-click `start.ps1` and run with PowerShell. Keep the terminal open while using the app; Ctrl+C stops the server.

## Install on another computer

Use Python 3.12. The application needs no GPU, API keys, or live delivery service.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`requirements.txt` pins the three direct dependencies; `requirements-lock.txt` captures the complete tested environment. The code and tests work offline after installation. Paths are resolved from the project folder, so the application does not depend on a particular terminal directory.

## Demonstrate each architecture separately

1. Select **Agent Lab**, then an agent architecture in the sidebar.
2. Select S1, S2, or S3. Use **Edit inputs and context** to create your own situation.
3. Press **Step** to execute one decision, or **Run to completion** for the entire delivery.
4. Inspect **Live workflow**, **Architecture**, and **Decision trace & replay**.
5. Replay is a read-only view of the stored trace; it does not execute actions or apply learning updates.
6. Download the trace JSON or architecture SVG. Use **History** to reopen saved runs.
7. **Reset delivery** creates a fresh independent run. It preserves learned policies.

### What distinguishes the agents

| Agent | Decision mechanism | Evidence to show |
|---|---|---|
| Simple Reflex | Current percept and ordered IF-THEN rules | Matched rule; no changing decision memory |
| Model-Based Reflex | Retained traffic beliefs and state-based rules | Current observation versus internal state |
| Goal-Based | Candidate plans that satisfy a deadline | Feasible plans and selected plan |
| Utility-Based | Maximum weighted utility | Score components and custom weight controls |
| Learning | Route values learned from actual outcomes | Counts, mean rewards, cold/trained evaluation |
| Hierarchical | Dependent delivery subgoals | Active task, completed tasks, recovery subtask |
| Contextual | Situational context and route eligibility | Night lighting, flood risk, food type, customer preferences |

## Three required common situations

- **S1**: normal traffic and clear weather; deadline 35 minutes.
- **S2**: heavy traffic with three routes; deadline 35 minutes.
- **S3**: heavy traffic, rain, and urgency; deadline 28 minutes.

In **Comparison**, press **Run 21 deliveries**. Each agent receives its own environment copy and the same pre-generated route-specific travel variation. The Learning Agent uses the latest saved policy unless cold-start evaluation is selected. Results record the policy version.

Route data is synthetic: A = 5 km/10 base minutes/100 cost units; B = 8 km/16 minutes/150 units; C = 6 km/12 minutes/120 units. All comparisons include preparation/handling and delivery confirmation. These values are demonstration parameters, not real-world estimates.

## Supplementary experiments

- **X1** hides Route A's traffic after an earlier observation. Inspect model-based memory and its 15-minute freshness limit.
- **X2** closes A at its first junction. Inspect rerouting and the hierarchy's recovery task.
- **X3** delays restaurant preparation. Verify that pickup is pending before travel.
- **X4** sets nighttime and economy preference. The Contextual Agent excludes unlit A, uses customer preference, and accounts for restaurant backlog.
- **X5** has an impossible deadline. Goal-Based reports infeasibility and attempts a fallback.
- **X6** closes every route. Agents report a terminal failure instead of inventing success.

## Learning demonstration

Open **Learning Lab** and train 20 samples per route/context: 180 episodes. Training systematically explores every route under the three contexts with seeded travel variation. The agent also implements epsilon-greedy exploration for additional programmatic training.

Training context: weather, overall traffic category, urgency. Learning update: `Q += (reward - Q) / sample_count`. Reward uses realized utility; failure receives -5. The chosen route receives feedback once per training delivery. Saved policy snapshots survive application restarts.

Press **Evaluate frozen policy**. By default it compares cold start and trained policy across 10 new seeds per scenario: 60 held-out deliveries. Exploration and updates are disabled. The summary includes deadline success, mean time, time variation, and mean reward. Fresh training intentionally explores poor routes, so an exploratory training curve alone is not proof of improvement.

## Utility definition

```text
U = -(wt * total_time/45 + wc * total_cost/200
      + wd * total_distance/10 + wg * traffic_multiplier/3)
    - 2 * max(0, total_time - deadline)/45
```

Standard weights: 0.45 time, 0.25 cost, 0.15 distance, 0.15 congestion. Urgent weights: 0.60, 0.15, 0.10, 0.15. Custom UI weights are normalized. Congestion overlaps with travel time by design as an extra preference; reference denominators are fixed demonstration scales. Rerouting includes sunk time/cost and a one-minute switch penalty. A 0.03 improvement threshold prevents unnecessary utility-based switches.

## Simulator conventions

Lifecycle: PLACED → ACCEPTED → ROUTE_SELECTED → PICKED_UP → IN_TRANSIT → ARRIVED → DELIVERED. Failure and timeout are alternative terminal outcomes.

Food becomes ready after preparation plus contextual backlog; pickup adds one handling minute by default. Confirmation adds two minutes. Route travel duration = base travel × traffic multiplier × weather multiplier × hidden seeded variation. Agents see the first three factors and cannot read the hidden variation.

The schematic assumes all routes share junctions at 0%, 25%, 50%, 75%, and 100%. Movement advances by up to a minute, ending exactly at a junction or scheduled event if sooner. Rerouting preserves progress, distance, and cost already incurred and adds a minute. This is a simplified simulation topology, not a real road network. A closure between reachable junctions ends with an explicit failure.

An action-count limit and 120-minute time limit prevent unproductive loops. Fractional final travel steps preserve exact fixture totals. Late delivery is distinct from delivery failure and is never labeled deadline success.

## Command-line tools

```powershell
.\.venv\Scripts\python.exe cli.py train --samples 20
.\.venv\Scripts\python.exe cli.py compare
.\.venv\Scripts\python.exe cli.py compare --cold-start --output outputs/cold_start_results.csv
.\.venv\Scripts\python.exe cli.py run --agent "Contextual" --scenario X4 --scenarios data/supplementary.json
.\.venv\Scripts\python.exe -m pytest -q
```

`cli.py reset-learning` clears saved policies while retaining delivery history. `scripts/generate_assets.py` regenerates the authored synthetic fixtures and diagrams; use it intentionally because it replaces these assets. `scripts/build_report.py` rebuilds the comparison report from the exported CSVs.

## Files and persistence

- `agents/`: seven algorithm implementations and common lifecycle helper.
- `core/`: validated models, environment, metrics, runner, SQLite storage.
- `data/`: common/supplementary JSON fixtures and `delivery.db`.
- `diagrams/`: seven editable Mermaid sources and seven standalone SVGs.
- `outputs/`: cold/trained comparison CSVs, training/evaluation CSVs, saved policy, JSON traces and screenshots.
- `report/COMPARISON.md`: generated measured comparison and conclusion.
- `IMPLEMENTATION_PLAN.md`: complete seven-agent design and implementation notes.
- `tests/`: architecture behavior, simulation, learning, storage and dashboard checks.

SQLite persists runs, unique steps, and policy snapshots using transactions. Saving a run again updates it instead of creating duplicates. UI session state preserves active objects across interface reruns. Resetting a browser session clears active in-memory runs; saved history remains accessible. The sidebar and inputs do not send messages, charge payments, or create real orders.

For a viva, explain architecture-specific evidence even when two agents choose the same route. State the scenario assumptions, tie-breaks, weights, and learning configuration. The three fixtures show behavior differences; they are not evidence that one architecture universally outperforms the others.
