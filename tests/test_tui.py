"""
tests/test_tui.py

Tests for the TUI components.
"""

from pathlib import Path
import pytest

from planner.tui.app import PlannerApp
from planner.tui.widgets.architecture_panel import ArchitecturePanel
from planner.tui.widgets.chat_input import ChatInput
from planner.tui.widgets.file_tree import PlannerFileTree
from planner.tui.widgets.viewer_panel import ViewerPanel


@pytest.mark.anyio
async def test_tui_layout_and_elements(tmp_path):
    """Test that all panels and components are instantiated and composed correctly."""
    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()

    app = PlannerApp(planner_path=planner_dir)
    async with app.run_test() as pilot:
        # Check that layout containers exist
        assert app.query_one(PlannerFileTree) is not None
        assert app.query_one(ArchitecturePanel) is not None
        assert app.query_one(ViewerPanel) is not None
        assert app.query_one(ChatInput) is not None

        # Check default titles
        assert app.query_one("#file-tree").border_title == "FILE VIEW"
        assert app.query_one("#architecture-panel").border_title == "ARCHITECTURE PANEL"
        assert app.query_one("#viewer-panel").border_title == "RESPONSE / VIEWER PANEL"
        assert app.query_one("#chat-input").border_title == "CHAT INPUT"


@pytest.mark.anyio
async def test_viewer_panel_modes(tmp_path):
    """Test ViewerPanel's rendering modes and write/clear/show_file methods."""
    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()
    test_file = planner_dir / "PRD.md"
    test_file.write_text("# Product Requirements\n- Feature A\n- Feature B", encoding="utf-8")

    app = PlannerApp(planner_path=planner_dir)
    async with app.run_test() as pilot:
        viewer = app.query_one(ViewerPanel)

        # 1. Output mode: write logs
        initial_count = len(viewer.output_buffer)
        viewer.write_output("Hello Log 1")
        viewer.write_output("Hello Log 2")
        assert viewer.mode == "output"
        assert len(viewer.output_buffer) == initial_count + 2

        # 2. File mode: show PRD
        viewer.show_file(test_file)
        assert viewer.mode == "file"

        # 3. Switching back: writing new output should restore output buffer + append new text
        viewer.write_output("Hello Log 3")
        assert viewer.mode == "output"
        assert len(viewer.output_buffer) == initial_count + 3

        assert viewer.output_buffer[-3:] == ["Hello Log 1", "Hello Log 2", "Hello Log 3"]

        # 4. Clear output
        viewer.clear_output()
        assert viewer.mode == "output"
        assert len(viewer.output_buffer) == 0


@pytest.mark.anyio
async def test_chat_input_command_submission(tmp_path):
    """Test that ChatInput submitted event translates to custom CommandSubmitted event."""
    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()

    app = PlannerApp(planner_path=planner_dir)
    async with app.run_test() as pilot:
        chat = app.query_one(ChatInput)
        viewer = app.query_one(ViewerPanel)

        # Let's write text to input and submit
        chat.value = "/help"
        await pilot.press("enter")

        # The input value should be cleared
        assert chat.value == ""

        # Viewer panel should display the help documentation
        await pilot.pause()
        assert any("Available Commands:" in line for line in viewer.output_buffer)


@pytest.mark.anyio
async def test_tui_interactive_input_patching(tmp_path):
    """Test that builtins.input is patched in run_in_background and gets unblocked by chat submissions."""
    import builtins
    import asyncio

    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()

    app = PlannerApp(planner_path=planner_dir)
    received_answer = None

    def worker_func():
        nonlocal received_answer
        received_answer = builtins.input("Enter something: ")

    async with app.run_test() as pilot:
        app.run_in_background(worker_func)

        # Wait a moment for worker to start and block
        await asyncio.sleep(0.1)
        assert app.waiting_for_input is True

        # Simulate user submitting an answer
        chat = app.query_one(ChatInput)
        chat.value = "my secret answer"
        await pilot.press("enter")

        # Wait for worker thread to finish
        await asyncio.sleep(0.2)
        assert app.waiting_for_input is False
        assert received_answer == "my secret answer"


@pytest.mark.anyio
async def test_tui_config_command(tmp_path):
    """Test that the /config slash command correctly prints configuration and handles settings."""
    from unittest.mock import patch
    import os

    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()

    app = PlannerApp(planner_path=planner_dir)

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        async with app.run_test() as pilot:
            chat = app.query_one(ChatInput)
            viewer = app.query_one(ViewerPanel)

            # 1. Test /config shows current status
            chat.value = "/config"
            await pilot.press("enter")
            await pilot.pause()
            
            assert any("Current LLM Configuration:" in line for line in viewer.output_buffer)
            assert any("API Keys Status:" in line for line in viewer.output_buffer)

            # 2. Test /config provider
            chat.value = "/config provider openai"
            await pilot.press("enter")
            await pilot.pause()
            assert any("Active provider set to: openai" in line for line in viewer.output_buffer)
            assert os.environ["ACTIVE_PROVIDER"] == "openai"

            # 3. Test /config model
            chat.value = "/config model gpt-4o-mini"
            await pilot.press("enter")
            await pilot.pause()
            assert any("Active model set to: gpt-4o-mini" in line for line in viewer.output_buffer)
            assert os.environ["ACTIVE_MODEL"] == "gpt-4o-mini"

            # 4. Test /config apikey
            chat.value = "/config apikey anthropic my-tui-key"
            await pilot.press("enter")
            await pilot.pause()
            assert any("API key for provider 'anthropic' successfully saved" in line for line in viewer.output_buffer)
            assert os.environ["ANTHROPIC_API_KEY"] == "my-tui-key"


@pytest.mark.anyio
async def test_tui_chat_orchestrator_routing(tmp_path):
    """Test that TUI routes conversational plain text entries through ChatOrchestrator."""
    from unittest.mock import patch
    import asyncio
    from planner.agents.chat_orchestrator import ChatAction

    planner_dir = tmp_path / "PLANNER"
    planner_dir.mkdir()

    app = PlannerApp(planner_path=planner_dir)

    mock_action = ChatAction(
        action="chat",
        response_message="Hello from the Conversational Orchestrator Brain!",
    )

    with patch("planner.agents.chat_orchestrator.chat_orchestrator", return_value=mock_action) as mock_chat:
        async with app.run_test() as pilot:
            chat = app.query_one(ChatInput)
            viewer = app.query_one(ViewerPanel)

            # Submit natural language chat message
            chat.value = "hello there"
            await pilot.press("enter")

            # Wait for background worker thread to execute
            await asyncio.sleep(0.2)

            mock_chat.assert_called_once()
            assert any("Hello from the Conversational Orchestrator Brain!" in line for line in viewer.output_buffer)
            assert len(app.chat_history) == 2




