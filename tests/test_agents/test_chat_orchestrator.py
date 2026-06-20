"""
tests/test_agents/test_chat_orchestrator.py

Tests for the ChatOrchestrator agent.
"""

from unittest.mock import MagicMock, patch
import pytest

from planner.agents.chat_orchestrator import chat_orchestrator, ChatAction


@patch("planner.agents.chat_orchestrator.get_llm")
def test_chat_orchestrator_resolves_chat_action(mock_get_llm):
    # Mock LLM and structured output
    mock_instance = MagicMock()
    mock_structured_llm = MagicMock()
    mock_get_llm.return_value = mock_instance
    mock_instance.with_structured_output.return_value = mock_structured_llm

    # Expected action returned by LLM
    expected_action = ChatAction(
        action="describe",
        text_content="build a to-do list app",
        response_message="Got it! I will begin describing and structuring your idea.",
    )
    mock_structured_llm.invoke.return_value = expected_action

    # Run orchestrator
    result = chat_orchestrator(
        user_message="i want to plan a to-do list app",
        chat_history=[],
        existing_files=[],
        active_file="",
    )

    # Assert correct invocation and result
    mock_instance.with_structured_output.assert_called_once_with(ChatAction)
    mock_structured_llm.invoke.assert_called_once()
    assert result.action == "describe"
    assert result.text_content == "build a to-do list app"
    assert result.response_message == "Got it! I will begin describing and structuring your idea."
