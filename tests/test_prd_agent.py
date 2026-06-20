import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from planner.state import PlannerState
from planner.agents.prd_agent import prd_agent
from planner.files.scaffold import scaffold_project

def test_prd_agent_missing_structured_idea(tmp_path):
    """
    Test that FileNotFoundError is raised if StructuredIdea.md does not exist.
    """
    # Create the directory but do not scaffold files
    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()
    
    state = PlannerState(project_path=str(planner_dir))
    with pytest.raises(FileNotFoundError):
        prd_agent(state)


def test_prd_agent_empty_structured_idea(tmp_path):
    """
    Test that prd_agent handles an empty StructuredIdea.md by pausing and setting status to 'needs_input'.
    """
    # Scaffold directories and files
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    
    # Verify StructuredIdea.md is empty initially
    structured_idea_path = planner_dir / "StructuredIdea.md"
    assert structured_idea_path.exists()
    assert structured_idea_path.stat().st_size == 0
    
    state = PlannerState(project_path=str(planner_dir))
    
    # Call prd_agent
    result_state = prd_agent(state)
    
    # Assert it returned early with pending_questions and status='needs_input'
    assert "empty" in result_state.pending_questions[0]
    assert result_state.status == "needs_input"
    assert result_state.current_file == "PRD.md"


@patch("planner.agents.prd_agent.get_llm")
def test_prd_agent_success(mock_get_llm, tmp_path):
    """
    Test that prd_agent correctly reads StructuredIdea.md, invokes LLM, and writes output to PRD.md.
    """
    # Scaffold project files
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    
    # Populate StructuredIdea.md and Constraints.md
    structured_idea_path = planner_dir / "StructuredIdea.md"
    structured_idea_path.write_text("Build a simple calculator web app.", encoding="utf-8")
    
    constraints_path = planner_dir / "Constraints.md"
    constraints_path.write_text("No external UI libraries allowed.", encoding="utf-8")
    
    # Mock LLM invocation
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "# Calculator PRD\n\nProblem Statement: Users need to compute numbers."
    mock_llm_instance.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm_instance
    
    state = PlannerState(project_path=str(planner_dir))
    
    # Run agent
    result_state = prd_agent(state)
    
    # Verify mock LLM was called
    mock_llm_instance.invoke.assert_called_once()
    
    # Check that PRD.md was written with mocked content
    prd_path = planner_dir / "PRD.md"
    assert prd_path.exists()
    assert prd_path.read_text(encoding="utf-8") == "# Calculator PRD\n\nProblem Statement: Users need to compute numbers."
    
    # Verify state updates
    assert result_state.current_file == "PRD.md"
    assert result_state.structured_idea == "Build a simple calculator web app."
    assert result_state.status == "drafting"


@patch("planner.agents.prd_agent.get_llm")
def test_prd_agent_markdown_stripping(mock_get_llm, tmp_path):
    """
    Test that prd_agent correctly strips markdown code block backticks surrounding the content.
    """
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    
    structured_idea_path = planner_dir / "StructuredIdea.md"
    structured_idea_path.write_text("Build a simple calculator web app.", encoding="utf-8")
    
    # Mock LLM invocation returning content wrapped in backticks
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "```markdown\n# Calculator PRD\nWritten inside codeblock\n```"
    mock_llm_instance.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm_instance
    
    state = PlannerState(project_path=str(planner_dir))
    
    # Run agent
    prd_agent(state)
    
    # Check that PRD.md was written with stripped content
    prd_path = planner_dir / "PRD.md"
    assert prd_path.exists()
    assert prd_path.read_text(encoding="utf-8") == "# Calculator PRD\nWritten inside codeblock"
