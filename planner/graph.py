"""
graph.py — Builds the LangGraph StateGraph for the PlannerX orchestration pipeline.

Node registry:
  orchestrator, structuring, prd, trd, schema, design, appflow,
  rules, implementation, tracker, modules, griller, tech_stack

Routing:
  - orchestrator reads state.next_agent to pick the next specialist.
  - Specialists route back to orchestrator when done, or to griller when needs_input.
  - griller routes to tech_stack (on '?') or back to calling_agent (on completion).
  - tech_stack always routes back to griller.
  - orchestrator routes to END when status == 'done'.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from planner.state import PlannerState
from planner.agents.orchestrator import orchestrator
from planner.agents.structuring_agent import structuring_agent
from planner.agents.prd_agent import prd_agent
from planner.agents.trd_agent import trd_agent
from planner.agents.schema_agent import schema_agent
from planner.agents.design_agent import design_agent
from planner.agents.appflow_agent import appflow_agent
from planner.agents.rules_agent import rules_agent
from planner.agents.implementation_agent import implementation_agent
from planner.agents.tracker_agent import tracker_agent
from planner.agents.griller_agent import griller_agent
from planner.agents.tech_stack_agent import tech_stack_agent
from planner.agents.module_planner_agent import module_planner_agent

# --------------------------------------------------------------------------- #
# Routing functions (read state, return next node name)
# --------------------------------------------------------------------------- #

def _route_from_orchestrator(state: PlannerState) -> str:
    """Orchestrator decides which specialist to invoke next (or END)."""
    if state.status == "done":
        return END
    agent = state.next_agent
    if agent in _VALID_NODES:
        return agent
    return END  # safety fallback


def _route_from_specialist(state: PlannerState) -> str:
    """After a specialist runs: go to griller if needs_input, else back to orchestrator."""
    if state.status == "needs_input":
        return "griller"
    return "orchestrator"


def _route_from_griller(state: PlannerState) -> str:
    """
    After griller runs:
      - next_agent == 'tech_stack'  → tech_stack_agent
      - else                        → calling_agent (resume the specialist that triggered grilling)
    """
    if state.next_agent == "tech_stack":
        return "tech_stack"
    # Resume the specialist that originally routed to griller
    target = state.next_agent or state.calling_agent
    if target and target in _VALID_NODES:
        return target
    return "orchestrator"


def _route_from_tech_stack(state: PlannerState) -> str:
    """TechStackExpert always routes back to griller to handle remaining questions."""
    return "griller"


# --------------------------------------------------------------------------- #
# Graph builder
# --------------------------------------------------------------------------- #

_VALID_NODES = {
    "orchestrator", "structuring", "prd", "trd", "schema",
    "design", "appflow", "rules", "implementation", "tracker",
    "modules", "griller", "tech_stack",
}

# Map state.next_agent value → graph node name (they match already, but explicit is safer)
_SPECIALIST_NODES = {
    "structuring", "prd", "trd", "schema",
    "design", "appflow", "rules", "implementation", "tracker", "modules",
}


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph.

    Returns a compiled graph that can be invoked with:
        graph.invoke(initial_state.model_dump())
    """
    # LangGraph requires TypedDict or dict; we pass PlannerState.model_dump()
    # and reconstruct PlannerState inside each node.
    # We use a thin wrapper so nodes receive/return dicts and we handle Pydantic internally.

    def _wrap(fn):
        """Wrap a PlannerState → PlannerState agent function to dict → dict for LangGraph."""
        def wrapped(state_dict: dict) -> dict:
            state = PlannerState(**state_dict)
            result = fn(state)
            return result.model_dump()
        wrapped.__name__ = fn.__name__
        return wrapped

    g = StateGraph(dict)  # LangGraph uses plain dict nodes

    # Register all nodes (wrapped for Pydantic ↔ dict conversion)
    g.add_node("orchestrator",    _wrap(orchestrator))
    g.add_node("structuring",     _wrap(structuring_agent))
    g.add_node("prd",             _wrap(prd_agent))
    g.add_node("trd",             _wrap(trd_agent))
    g.add_node("schema",          _wrap(schema_agent))
    g.add_node("design",          _wrap(design_agent))
    g.add_node("appflow",         _wrap(appflow_agent))
    g.add_node("rules",           _wrap(rules_agent))
    g.add_node("implementation",  _wrap(implementation_agent))
    g.add_node("tracker",         _wrap(tracker_agent))
    g.add_node("modules",         _wrap(module_planner_agent))
    g.add_node("griller",         _wrap(griller_agent))
    g.add_node("tech_stack",      _wrap(tech_stack_agent))

    # Entry point
    g.set_entry_point("orchestrator")

    # Orchestrator: conditional routing to any specialist or END
    g.add_conditional_edges(
        "orchestrator",
        lambda s: _route_from_orchestrator(PlannerState(**s)),
        {name: name for name in _VALID_NODES} | {END: END},
    )

    # All specialists route back to orchestrator (or griller if needs_input)
    for node in _SPECIALIST_NODES:
        g.add_conditional_edges(
            node,
            lambda s: _route_from_specialist(PlannerState(**s)),
            {"orchestrator": "orchestrator", "griller": "griller"},
        )

    # Griller: routes to tech_stack or back to calling specialist
    g.add_conditional_edges(
        "griller",
        lambda s: _route_from_griller(PlannerState(**s)),
        {name: name for name in _VALID_NODES},
    )

    # TechStackExpert: always back to griller
    g.add_edge("tech_stack", "griller")

    return g.compile()


def run_graph(project_path: str) -> PlannerState:
    """
    Convenience function used by the CLI `planner run` command.
    Initialises state and runs the compiled graph to completion.
    Returns the final PlannerState.
    """
    from planner.files.reader import read_planner_file
    from pathlib import Path

    planner_dir = Path(project_path)
    if not planner_dir.exists():
        raise FileNotFoundError(
            f"PLANNER directory not found at {planner_dir}. Run `planner init` first."
        )

    # Pre-load StructuredIdea if it exists
    si_path = planner_dir / "StructuredIdea.md"
    structured_idea = read_planner_file(si_path, use_cache=False).strip() if si_path.exists() else ""

    initial_state = PlannerState(
        project_path=str(planner_dir),
        structured_idea=structured_idea,
    )

    graph = build_graph()
    result_dict = graph.invoke(initial_state.model_dump())
    return PlannerState(**result_dict)
