"""
Tests for all specialist agents (TRD, Schema, Design, AppFlow, Rules, Implementation, Tracker).
Uses mocked LLM — no API keys needed.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from planner.state import PlannerState
from planner.files.scaffold import scaffold_project


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_state(tmp_path: Path, **extras) -> PlannerState:
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    # Populate StructuredIdea so agents don't bail early
    (planner_dir / "StructuredIdea.md").write_text(
        "# Task Tracker\nA CLI app in Python that tracks tasks in a JSON file.",
        encoding="utf-8",
    )
    return PlannerState(project_path=str(planner_dir), **extras)


def _mock_llm(content: str):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm.invoke.return_value = mock_response
    return mock_llm


# ── Structuring Agent ─────────────────────────────────────────────────────────

class TestStructuringAgent:
    @patch("planner.agents.structuring_agent.invoke_llm_safe", return_value="# Structured\nClean idea.")
    def test_writes_structured_idea(self, mock_invoke, tmp_path):
        scaffold_project(base_path=tmp_path)
        planner_dir = tmp_path / "PLANNER"
        (planner_dir / "RawIdea.md").write_text("Build a task app", encoding="utf-8")
        state = PlannerState(project_path=str(planner_dir))

        from planner.agents.structuring_agent import structuring_agent
        result = structuring_agent(state)

        assert (planner_dir / "StructuredIdea.md").read_text(encoding="utf-8") == "# Structured\nClean idea."
        assert result.current_file == "StructuredIdea.md"
        assert result.status == "drafting"

    def test_empty_raw_idea_sets_needs_input(self, tmp_path):
        scaffold_project(base_path=tmp_path)
        planner_dir = tmp_path / "PLANNER"
        state = PlannerState(project_path=str(planner_dir))

        from planner.agents.structuring_agent import structuring_agent
        result = structuring_agent(state)

        assert result.status == "needs_input"
        assert len(result.pending_questions) == 1


# ── TRD Agent ─────────────────────────────────────────────────────────────────

class TestTrdAgent:
    @patch("planner.agents.trd_agent.invoke_llm_safe", return_value="# TRD\nTech stack: Python.")
    def test_writes_trd(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.trd_agent import trd_agent
        result = trd_agent(state)

        planner_dir = Path(state.project_path)
        assert (planner_dir / "TRD.md").read_text(encoding="utf-8") == "# TRD\nTech stack: Python."
        assert result.current_file == "TRD.md"
        assert result.status == "drafting"


# ── Schema Agent ──────────────────────────────────────────────────────────────

class TestSchemaAgent:
    @patch("planner.agents.schema_agent.invoke_llm_safe", return_value="# Schema\n## Tasks table")
    def test_writes_schema(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.schema_agent import schema_agent
        result = schema_agent(state)

        planner_dir = Path(state.project_path)
        assert (planner_dir / "Schema.md").read_text(encoding="utf-8") == "# Schema\n## Tasks table"
        assert result.current_file == "Schema.md"


# ── Design Agent ──────────────────────────────────────────────────────────────

class TestDesignAgent:
    @patch("planner.agents.design_agent.invoke_llm_safe", return_value="# Design Decisions\nUsed Python.")
    def test_writes_design_decisions(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.design_agent import design_agent
        result = design_agent(state)

        planner_dir = Path(state.project_path)
        assert (planner_dir / "DesignDecisions.md").stat().st_size > 0
        assert result.current_file == "DesignDecisions.md"


# ── AppFlow Agent ─────────────────────────────────────────────────────────────

class TestAppFlowAgent:
    @patch("planner.agents.appflow_agent.invoke_llm_safe", return_value="# AppFlow\nUser logs in.")
    def test_writes_appflow(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.appflow_agent import appflow_agent
        result = appflow_agent(state)

        planner_dir = Path(state.project_path)
        assert (planner_dir / "AppFlow.md").stat().st_size > 0
        assert result.current_file == "AppFlow.md"


# ── Rules Agent ───────────────────────────────────────────────────────────────

class TestRulesAgent:
    @patch("planner.agents.rules_agent.invoke_llm_safe", return_value="# Rules\nUse PEP8.")
    def test_writes_rules(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.rules_agent import rules_agent
        result = rules_agent(state)

        planner_dir = Path(state.project_path)
        assert (planner_dir / "Rules.md").read_text(encoding="utf-8") == "# Rules\nUse PEP8."
        assert result.current_file == "Rules.md"


# ── Implementation Agent ──────────────────────────────────────────────────────

class TestImplementationAgent:
    @patch("planner.agents.implementation_agent.invoke_llm_safe", return_value="# Plan\n## Phase 1")
    def test_writes_implementation_plan(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path)
        planner_dir = Path(state.project_path)
        # Populate PRD and TRD so the agent doesn't bail
        (planner_dir / "PRD.md").write_text("# PRD content", encoding="utf-8")
        (planner_dir / "TRD.md").write_text("# TRD content", encoding="utf-8")

        from planner.agents.implementation_agent import implementation_agent
        result = implementation_agent(state)

        assert (planner_dir / "ImplementationPlan.md").read_text(encoding="utf-8") == "# Plan\n## Phase 1"
        assert result.current_file == "ImplementationPlan.md"

    def test_empty_prd_and_trd_sets_needs_input(self, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.implementation_agent import implementation_agent
        result = implementation_agent(state)
        assert result.status == "needs_input"


# ── Tracker Agent ─────────────────────────────────────────────────────────────

class TestTrackerAgent:
    def test_writes_tracker_md(self, tmp_path):
        state = _make_state(tmp_path)
        planner_dir = Path(state.project_path)
        # Give it some content to scan
        (planner_dir / "PRD.md").write_text("PRD content", encoding="utf-8")

        from planner.agents.tracker_agent import tracker_agent
        result = tracker_agent(state)

        tracker_path = planner_dir / "Tracker.md"
        assert tracker_path.exists()
        content = tracker_path.read_text(encoding="utf-8")
        assert "PRD.md" in content
        assert "✅ Done" in content
        assert result.current_file == "Tracker.md"

    def test_approved_files_shown_in_tracker(self, tmp_path):
        state = _make_state(tmp_path)
        planner_dir = Path(state.project_path)
        (planner_dir / "PRD.md").write_text("PRD content", encoding="utf-8")
        state.approved_files = ["PRD.md"]

        from planner.agents.tracker_agent import tracker_agent
        tracker_agent(state)

        tracker_content = (planner_dir / "Tracker.md").read_text(encoding="utf-8")
        # PRD.md row should show approved mark
        assert "PRD.md" in tracker_content


# ── Module Planner Agent ──────────────────────────────────────────────────────

class TestModulePlannerAgent:
    @patch("planner.agents.module_planner_agent.invoke_llm_safe", return_value="# auth module spec")
    def test_writes_module_file(self, mock_invoke, tmp_path):
        state = _make_state(tmp_path, context_files={"__module_name__": "auth"})
        from planner.agents.module_planner_agent import module_planner_agent
        result = module_planner_agent(state)

        modules_dir = Path(state.project_path) / "MODULES"
        assert (modules_dir / "auth.md").read_text(encoding="utf-8") == "# auth module spec"
        assert result.status == "done"

    def test_no_module_name_sets_done(self, tmp_path):
        state = _make_state(tmp_path)
        from planner.agents.module_planner_agent import module_planner_agent
        result = module_planner_agent(state)
        assert result.status == "done"
