"""Seven independent, inspectable agent architectures."""
from agents.simple_reflex import SimpleReflexAgent
from agents.model_based import ModelBasedAgent
from agents.goal_based import GoalBasedAgent
from agents.utility_based import UtilityBasedAgent
from agents.learning import LearningAgent
from agents.hierarchical import HierarchicalAgent
from agents.contextual import ContextualAgent

AGENTS = {
    "Simple Reflex": SimpleReflexAgent,
    "Model-Based Reflex": ModelBasedAgent,
    "Goal-Based": GoalBasedAgent,
    "Utility-Based": UtilityBasedAgent,
    "Learning": LearningAgent,
    "Hierarchical": HierarchicalAgent,
    "Contextual": ContextualAgent,
}

DESCRIPTIONS = {
    "Simple Reflex": "Acts on the current percept through ordered IF-THEN rules.",
    "Model-Based Reflex": "Updates internal beliefs before applying state-based rules.",
    "Goal-Based": "Searches for a delivery plan that satisfies the deadline.",
    "Utility-Based": "Ranks predicted outcomes using explicit time, cost, distance and congestion preferences.",
    "Learning": "Uses delivery feedback to update route values and improve future choices.",
    "Hierarchical": "Decomposes delivery into dependent subgoals and recovery tasks.",
    "Contextual": "Collects situational context and adapts its route policy to it.",
}

SLUGS = {name: name.lower().replace("-", "_").replace(" ", "_") for name in AGENTS}
