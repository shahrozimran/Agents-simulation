"""Generate synthetic fixtures and portable, code-native architecture diagrams."""
import json
from pathlib import Path
import sys
from textwrap import wrap
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents import AGENTS, SLUGS
from core.models import Route, Scenario


def scenarios():
    routes = [Route("A", 5, 10, 100, well_lit=False, flood_risk=.8),
              Route("B", 8, 16, 150, well_lit=True, flood_risk=.1),
              Route("C", 6, 12, 120, well_lit=True, flood_risk=.3)]
    s1 = Scenario("S1", "Normal traffic / clear weather", routes)
    s2 = s1.clone()
    s2.scenario_id, s2.name = "S2", "Heavy traffic / alternative routes"
    for route, multiplier, label in zip(s2.routes, [2.2, 1.1, 1.3], ["heavy", "light", "moderate"]):
        route.traffic_multiplier, route.traffic = multiplier, label
    s3 = s2.clone()
    s3.scenario_id, s3.name = "S3", "Heavy traffic / rain / urgent delivery"
    s3.weather, s3.weather_multiplier, s3.urgent, s3.deadline_min = "rain", 1.25, True, 28
    common = [s1, s2, s3]
    memory = s1.clone()
    memory.scenario_id, memory.name = "X1", "Memory / traffic observation disappears"
    memory.events = [{"time": 0, "kind": "traffic", "route_id": "A", "label": "heavy", "multiplier": 2.2},
                     {"time": 0, "kind": "traffic", "route_id": "B", "label": "heavy", "multiplier": 2.0},
                     {"time": 0, "kind": "traffic", "route_id": "C", "label": "heavy", "multiplier": 1.8},
                     {"time": 6, "kind": "hide", "route_id": "A"}]
    closure = s1.clone()
    closure.scenario_id, closure.name = "X2", "Recovery / Route A closes at first junction"
    closure.events = [{"time": 7.5, "kind": "close", "route_id": "A"}]
    prep = s1.clone()
    prep.scenario_id, prep.name, prep.prep_min = "X3", "Hierarchy / restaurant preparation delay", 12
    night = s1.clone()
    night.scenario_id, night.name = "X4", "Context / night delivery with economy preference"
    night.context.update(time_of_day="night", customer_preference="economy", restaurant_backlog_min=3)
    impossible = s3.clone()
    impossible.scenario_id, impossible.name, impossible.deadline_min = "X5", "Goal / impossible deadline", 8
    blocked = s1.clone()
    blocked.scenario_id, blocked.name = "X6", "Failure / all routes closed"
    for route in blocked.routes:
        route.available = False
    for collection, filename in [(common, "scenarios.json"), ([memory, closure, prep, night, impossible, blocked], "supplementary.json")]:
        (ROOT / "data" / filename).write_text(json.dumps([s.validate().to_dict() for s in collection], indent=2), encoding="utf-8")


EXTRA = {
    "Simple Reflex": ("Fixed rule priority", "IF traffic is heavy, choose first non-heavy alternative"),
    "Model-Based Reflex": ("Internal state", "Previous observations, status and transition model"),
    "Goal-Based": ("Goal and deadline", "Deliver successfully before the required time"),
    "Utility-Based": ("Utility preferences", "Normalize time, cost, distance and congestion"),
    "Learning": ("Learned route values", "Update mean reward from completed deliveries"),
    "Hierarchical": ("Delivery subgoals", "Accept / route / pickup / deliver / confirm"),
    "Contextual": ("Collected context", "Night, food type, rain risk and customer preference"),
}
DECISIONS = {
    "Simple Reflex": "Match IF-THEN rules", "Model-Based Reflex": "Update beliefs then apply rules",
    "Goal-Based": "Generate and select a feasible plan", "Utility-Based": "Select maximum utility",
    "Learning": "Explore or exploit route values", "Hierarchical": "Execute active subgoal",
    "Contextual": "Filter routes and adapt policy",
}


def box(x, y, w, h, title, subtitle="", accent=False):
    fill = "#E1F2EB" if accent else "#FFFFFF"
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#B8D3C7"/>']
    lines = wrap(title, 23)
    if subtitle:
        lines += wrap(subtitle, 30)
    for i, line in enumerate(lines):
        size = 16 if i < len(wrap(title, 23)) else 12
        parts.append(f'<text x="{x+w/2}" y="{y+26+i*20}" text-anchor="middle" fill="#19372E" font-family="Arial,sans-serif" font-size="{size}">{escape(line)}</text>')
    return "".join(parts)


def arrow(points, label=""):
    result = f'<polyline points="{points}" fill="none" stroke="#137D70" stroke-width="2" marker-end="url(#arrow)"/>'
    if label:
        result += f'<text x="600" y="400" font-family="Arial,sans-serif" font-size="13" fill="#587167">{escape(label)}</text>'
    return result


def diagrams():
    for name in AGENTS:
        component, explanation = EXTRA[name]
        body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="470" viewBox="0 0 1020 470"><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#137D70"/></marker></defs><rect width="1020" height="470" rx="18" fill="#F6FAF7"/><text x="35" y="40" font-family="Arial,sans-serif" font-size="24" font-weight="bold" fill="#19372E">{escape(name)} Agent</text>',
                box(35, 230, 170, 110, "Input / perception", "Order and visible conditions"),
                box(300, 230, 220, 110, DECISIONS[name], accent=True),
                box(610, 230, 160, 110, "Action", "Selected delivery operation"),
                box(850, 230, 145, 110, "Environment", "Execute and observe"),
                box(300, 75, 270, 125, component, explanation, accent=True),
                arrow("205,285 300,285"), arrow("520,285 610,285"), arrow("770,285 850,285"),
                arrow("410,200 410,230"), arrow("922,340 922,425 120,425 120,340")]
        mermaid = f"flowchart LR\n    P[Input / perception] --> D[{DECISIONS[name]}]\n    D --> A[Action]\n    A --> E[Environment]\n    E --> P\n    C[{component}] --> D\n"
        if name == "Model-Based Reflex":
            body.append(arrow("520,248 590,248 590,175 570,175"))
            mermaid += "    P --> C\n    D --> C\n"
        if name == "Learning":
            body += [box(735, 75, 260, 125, "Outcome / reward", "Delivery feedback and critic"),
                     arrow("922,230 922,200"), arrow("735,135 570,135")]
            mermaid += "    E --> R[Outcome / reward]\n    R --> C\n"
        if name == "Hierarchical":
            body.append(arrow("520,248 590,248 590,175 570,175"))
            mermaid += "    E --> V[Validate subgoal]\n    V --> C\n"
        if name == "Contextual":
            mermaid += "    X[External situational signals] --> C\n"
        body.append('<text x="35" y="457" font-family="Arial,sans-serif" font-size="12" fill="#587167">Single independent agent. Feedback returns observations for the next decision.</text></svg>')
        slug = SLUGS[name]
        (ROOT / "diagrams" / f"{slug}.svg").write_text("".join(body), encoding="utf-8")
        (ROOT / "diagrams" / f"{slug}.mmd").write_text(mermaid, encoding="utf-8")


if __name__ == "__main__":
    for name in ["data", "diagrams", "outputs", "outputs/traces", "outputs/screenshots", "report"]:
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    scenarios()
    diagrams()
    print("Created three common scenarios, six supplementary scenarios, and seven SVG/Mermaid diagrams.")
