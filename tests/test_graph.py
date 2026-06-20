"""
Tests for graph.py — routing logic, conditional edges, and the full
Griller → TechStackExpert → resume path.

All agent nodes are mocked — we're testing the routing/wiring only.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from planner.state import PlannerState
from planner.files.scaffold import scaffold_project


def _make_planner_dir(tmp_path: Path) -> Path:
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    (planner_dir / "StructuredIdea.md").write_text(
        "A CLI task tracker app.", encoding="utf-8"
    )
    return planner_dir


# ── Routing function unit tests (no full graph compile) ──────────────────────

class TestRoutingFunctions:
    def test_orchestrator_routes_to_end_when_done(self, tmp_path):
        """_route_from_orchestrator should return END when status == 'done'."""
        from planner.graph import _route_from_orchestrator
        from langgraph.graph import END
        state = PlannerState(
            project_path=str(tmp_path / "PLANNER"),
            status="done",
            next_agent="",
        )
        assert _route_from_orchestrator(state) == END

    def test_orchestrator_routes_to_next_agent(self, tmp_path):
        """_route_from_orchestrator should return state.next_agent when not done."""
        from planner.graph import _route_from_orchestrator
        state = PlannerState(
            project_path=str(tmp_path / "PLANNER"),
            status="drafting",
            next_agent="prd",
        )
        assert _route_from_orchestrator(state) == "prd"

    def test_specialist_routes_to_griller_on_needs_input(self, tmp_path):
        from planner.graph import _route_from_specialist
        state = PlannerState(
            project_path=str(tmp_path / "PLANNER"),
            status="needs_input",
        )
        assert _route_from_specialist(state) == "griller"

    def test_specialist_routes_to_orchestrator_when_done(self, tmp_path):
        from planner.graph import _route_from_specialist
        state = PlannerState(
            project_path=str(tmp_path / "PLANNER"),
            status="drafting",
        )
        assert _route_from_specialist(state) == "orchestrator"

    def test_griller_routes_to_tech_stack_on_question_mark(self, tmp_path):
        from planner.graph import _route_from_griller
        state = PlannerState(
            project_path=str(tmp_path / "PLANNER"),
            next_agent="tech_stack",
            calling_agent="trd",
        )
        assert _route_from_griller(state) == "tech_stack"

    def test_griller_routes_to_calling_agent_when_done(self, tmp_path):
        from planner.graph import _route_from_griller
        state = PlannerState(
            project_path=str(tmp_path / "PLANNER"),
            next_agent="trd",
            calling_agent="trd",
        )
        assert _route_from_griller(state) == "trd"

    def test_tech_stack_always_routes_to_griller(self, tmp_path):
        from planner.graph import _route_from_tech_stack
        state = PlannerState(project_path=str(tmp_path / "PLANNER"))
        assert _route_from_tech_stack(state) == "griller"


# ── Orchestrator logic tests ──────────────────────────────────────────────────

class TestOrchestratorLogic:
    def test_routes_to_structuring_when_structured_idea_empty(self, tmp_path):
        planner_dir = tmp_path / "PLANNER"
        scaffold_project(base_path=tmp_path)
        # StructuredIdea.md is empty after scaffolding
        state = PlannerState(project_path=str(planner_dir))

        from planner.agents.orchestrator import orchestrator
        result = orchestrator(state)
        assert result.next_agent == "structuring"

    def test_routes_to_prd_when_structured_idea_exists(self, tmp_path):
        planner_dir = _make_planner_dir(tmp_path)
        state = PlannerState(project_path=str(planner_dir))

        from planner.agents.orchestrator import orchestrator
        result = orchestrator(state)
        assert result.next_agent == "prd"

    def test_skips_design_and_appflow_for_backend_only(self, tmp_path):
        planner_dir = tmp_path / "PLANNER"
        scaffold_project(base_path=tmp_path)
        # Backend-only project — no frontend keywords
        (planner_dir / "StructuredIdea.md").write_text(
            "A pure REST API backend with no UI, no frontend, no browser.", encoding="utf-8"
        )
        # Populate everything up to Schema.md
        for fname in ["PRD.md", "TRD.md", "Schema.md"]:
            (planner_dir / fname).write_text(f"# {fname} content", encoding="utf-8")

        state = PlannerState(project_path=str(planner_dir))
        from planner.agents.orchestrator import orchestrator
        result = orchestrator(state)

        # Should skip design/appflow and go to rules
        assert result.next_agent == "rules"
        assert result.has_frontend is False

    def test_does_not_skip_design_for_frontend_project(self, tmp_path):
        planner_dir = tmp_path / "PLANNER"
        scaffold_project(base_path=tmp_path)
        (planner_dir / "StructuredIdea.md").write_text(
            "A React web app dashboard with a frontend UI.", encoding="utf-8"
        )
        for fname in ["PRD.md", "TRD.md", "Schema.md"]:
            (planner_dir / fname).write_text(f"# {fname} content", encoding="utf-8")

        state = PlannerState(project_path=str(planner_dir))
        from planner.agents.orchestrator import orchestrator
        result = orchestrator(state)

        assert result.next_agent == "design"
        assert result.has_frontend is True

    def test_returns_done_when_all_files_populated(self, tmp_path):
        planner_dir = tmp_path / "PLANNER"
        scaffold_project(base_path=tmp_path)
        # Backend-only: populate all required files
        (planner_dir / "StructuredIdea.md").write_text("pure backend api", encoding="utf-8")
        for fname in ["PRD.md", "TRD.md", "Schema.md", "Rules.md", "ImplementationPlan.md", "Tracker.md"]:
            (planner_dir / fname).write_text(f"# {fname}", encoding="utf-8")

        state = PlannerState(project_path=str(planner_dir))
        from planner.agents.orchestrator import orchestrator
        result = orchestrator(state)
        assert result.status == "done"


# ── Graph build smoke test ────────────────────────────────────────────────────

class TestGraphBuilds:
    def test_graph_compiles_without_error(self):
        """build_graph() should compile without raising exceptions."""
        from planner.graph import build_graph
        graph = build_graph()
        assert graph is not None
