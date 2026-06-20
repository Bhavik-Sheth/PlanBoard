"""
Tests for the Griller and TechStackExpert interaction agents.
Uses mocked input() and LLM calls.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from planner.state import PlannerState
from planner.files.scaffold import scaffold_project


def _make_state(tmp_path: Path, **extras) -> PlannerState:
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    return PlannerState(project_path=str(planner_dir), **extras)


# ── Griller Agent ─────────────────────────────────────────────────────────────

class TestGrillerAgent:
    @patch("builtins.input", return_value="Python with sqlite3")
    def test_answers_all_questions(self, mock_input, tmp_path):
        """Griller should fill grill_answers and route back to calling_agent."""
        state = _make_state(
            tmp_path,
            pending_questions=["What database should we use?"],
            calling_agent="trd",
        )
        from planner.agents.griller_agent import griller_agent
        result = griller_agent(state)

        assert result.grill_answers == {"What database should we use?": "Python with sqlite3"}
        assert result.pending_questions == []
        assert result.status == "drafting"
        assert result.next_agent == "trd"

    @patch("builtins.input", return_value="?")
    def test_routes_to_tech_stack_on_question_mark(self, mock_input, tmp_path):
        """Typing '?' should route to tech_stack and preserve remaining questions."""
        state = _make_state(
            tmp_path,
            pending_questions=["What database?", "What auth method?"],
            calling_agent="trd",
        )
        from planner.agents.griller_agent import griller_agent
        result = griller_agent(state)

        assert result.next_agent == "tech_stack"
        assert "What database?" in result.tech_suggestions.get("__current_question__", "")
        # pending_questions should still contain the unanswered ones
        assert len(result.pending_questions) >= 1

    def test_no_questions_routes_back_immediately(self, tmp_path):
        """With no pending questions, griller should immediately resume calling_agent."""
        state = _make_state(tmp_path, pending_questions=[], calling_agent="schema")
        from planner.agents.griller_agent import griller_agent
        result = griller_agent(state)

        assert result.status == "drafting"
        assert result.next_agent == "schema"


# ── TechStackExpert Agent ─────────────────────────────────────────────────────

class TestTechStackAgent:
    @patch("builtins.input", return_value="y")
    @patch("planner.agents.tech_stack_agent.invoke_llm_safe", return_value="Use SQLite — lightweight and no setup.")
    def test_accepts_suggestion(self, mock_llm, mock_input, tmp_path):
        """User accepts the suggestion → answer goes into grill_answers."""
        state = _make_state(
            tmp_path,
            pending_questions=["What database?"],
            tech_suggestions={"__current_question__": "What database?"},
            calling_agent="trd",
        )
        from planner.agents.tech_stack_agent import tech_stack_agent
        result = tech_stack_agent(state)

        assert "What database?" in result.grill_answers
        assert "SQLite" in result.grill_answers["What database?"]
        assert result.next_agent == "griller"
        assert "__current_question__" not in result.tech_suggestions

    @patch("builtins.input", side_effect=["n", "PostgreSQL is fine"])
    @patch("planner.agents.tech_stack_agent.invoke_llm_safe", return_value="Use SQLite.")
    def test_rejects_suggestion_and_enters_custom(self, mock_llm, mock_input, tmp_path):
        """User rejects the suggestion and types a custom answer."""
        state = _make_state(
            tmp_path,
            pending_questions=["What database?"],
            tech_suggestions={"__current_question__": "What database?"},
            calling_agent="trd",
        )
        from planner.agents.tech_stack_agent import tech_stack_agent
        result = tech_stack_agent(state)

        assert result.grill_answers.get("What database?") == "PostgreSQL is fine"
        assert result.next_agent == "griller"

    def test_no_current_question_routes_to_griller(self, tmp_path):
        """If __current_question__ is missing, route back to griller immediately."""
        state = _make_state(tmp_path, tech_suggestions={})
        from planner.agents.tech_stack_agent import tech_stack_agent
        result = tech_stack_agent(state)
        assert result.next_agent == "griller"
