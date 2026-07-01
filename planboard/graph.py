"""
graph.py — Builds the LangGraph StateGraph for the PlanBoard orchestration pipeline.

Node registry:
  orchestrator, structuring, constraints, prd, trd, schema, design, appflow,
  rules, implementation, modules, griller, tech_stack

Removed from graph:
  tracker — demoted to tracker_tools direct calls inside orchestrator handlers

Routing:
  - orchestrator reads state.next_agent to pick the next specialist.
  - Specialists route back to orchestrator when done, or to griller when needs_input.
  - griller routes to tech_stack (on '?') or back to calling_agent (on completion).
  - tech_stack always routes back to griller.
  - orchestrator routes to END when status == 'done'.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from planboard.state import PlannerState, load_state, save_state
from planboard.agents.orchestrator import orchestrator
from planboard.agents.structuring_agent import structuring_agent
from planboard.agents.constraints_agent import constraints_agent
from planboard.agents.prd_agent import prd_agent
from planboard.agents.trd_agent import trd_agent
from planboard.agents.schema_agent import schema_agent
from planboard.agents.design_agent import design_agent
from planboard.agents.appflow_agent import appflow_agent
from planboard.agents.rules_agent import rules_agent
from planboard.agents.implementation_agent import implementation_agent
from planboard.agents.griller_agent import griller_agent
from planboard.agents.tech_stack_agent import tech_stack_agent
from planboard.agents.module_planboard_agent import module_planboard_agent

# --------------------------------------------------------------------------- #
# Routing functions (read state, return next node name)
# --------------------------------------------------------------------------- #

def _route_from_orchestrator(state: PlannerState) -> str:
    """Orchestrator decides which specialist to invoke next (or END)."""
    if state.status == "done":
        return END
    if state.status == "needs_review":
        return END  # Pause for user review/approval
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

# Valid nodes in the graph (tracker removed — demoted to tool calls)
_VALID_NODES = {
    "orchestrator", "structuring", "constraints", "prd", "trd", "schema",
    "design", "appflow", "rules", "implementation",
    "modules", "griller", "tech_stack",
}

# Specialist nodes that route back through orchestrator or to griller
_SPECIALIST_NODES = {
    "structuring", "constraints", "prd", "trd", "schema",
    "design", "appflow", "rules", "implementation", "modules",
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
            try:
                result = fn(state)
                return result.model_dump()
            except Exception as exc:
                from pathlib import Path
                from planboard.tools.tracker_tools import update_file_status, add_blocker
                project_root = str(Path(state.project_path).parent)
                filename = state.current_file or "unknown"
                agent_name = fn.__name__
                try:
                    update_file_status(
                        project_root,
                        filename,
                        "❌ Blocked",
                        agent_name,
                        notes=str(exc)
                    )
                    add_blocker(
                        project_root,
                        f"Agent {agent_name} failed: {exc}",
                        unblocked_by="re-run /run"
                    )
                except Exception:
                    pass
                state.status = "error"
                state.error_message = str(exc)
                save_state(state)
                raise exc
        wrapped.__name__ = fn.__name__
        return wrapped

    g = StateGraph(dict)  # LangGraph uses plain dict nodes

    # Register all nodes (wrapped for Pydantic ↔ dict conversion)
    # NOTE: tracker node is REMOVED — tracker updates are now direct
    #       tracker_tools calls inside orchestrator command handlers
    g.add_node("orchestrator",    _wrap(orchestrator))
    g.add_node("structuring",     _wrap(structuring_agent))
    g.add_node("constraints",     _wrap(constraints_agent))
    g.add_node("prd",             _wrap(prd_agent))
    g.add_node("trd",             _wrap(trd_agent))
    g.add_node("schema",          _wrap(schema_agent))
    g.add_node("design",          _wrap(design_agent))
    g.add_node("appflow",         _wrap(appflow_agent))
    g.add_node("rules",           _wrap(rules_agent))
    g.add_node("implementation",  _wrap(implementation_agent))
    g.add_node("modules",         _wrap(module_planboard_agent))
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

    from langgraph.checkpoint.memory import InMemorySaver
    checkpointer = InMemorySaver()
    return g.compile(checkpointer=checkpointer, interrupt_before=["griller"])


def run_graph(project_path: str) -> PlannerState:
    """
    Convenience function used by the CLI `planboard run` command.
    Initialises state and runs the compiled graph to completion.
    Returns the final PlannerState.
    """
    from pathlib import Path
    from planboard.watcher.watcher_manager import WatcherManager

    planboard_dir = Path(project_path)
    if not planboard_dir.exists():
        raise FileNotFoundError(
            f"PLANBOARD directory not found at {planboard_dir}. Run `planboard init` first."
        )

    lock_path = planboard_dir / ".graph_running"
    wm = WatcherManager(project_path)
    
    try:
        lock_path.write_text("running", encoding="utf-8")
        wm.restart_if_dead()

        # Load state from disk
        state = load_state(project_path)

        graph = build_graph()
        config = {"configurable": {"thread_id": "1"}}
        result_dict = graph.invoke(state.model_dump(), config)
        
        final_state = PlannerState(**result_dict)
        
        # Save state back to disk
        save_state(final_state)
        return final_state
    finally:
        if lock_path.exists():
            try:
                lock_path.unlink()
            except Exception:
                pass
