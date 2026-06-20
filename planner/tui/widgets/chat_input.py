"""
planner/tui/widgets/chat_input.py

ChatInput — bottom-right panel that takes user commands and chat messages.
Extends Input and posts a custom CommandSubmitted message when the user hits Enter.
"""

from textual.message import Message
from textual.widgets import Input


class ChatInput(Input):
    """Input panel for typing commands and messages."""

    class CommandSubmitted(Message):
        """Custom message posted when a command is submitted."""
        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle default Input submission and post custom CommandSubmitted message."""
        command = event.value.strip()
        if command:
            self.post_message(self.CommandSubmitted(command))
        self.value = ""
