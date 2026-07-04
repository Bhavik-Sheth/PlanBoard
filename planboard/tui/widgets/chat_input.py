"""
planboard/tui/widgets/chat_input.py

ChatInput — bottom-right panel that takes user commands and chat messages.
Extends TextArea and posts a custom CommandSubmitted message when the user hits Enter.
Supports autocomplete for slash commands and project files.
"""

import re
from textual.message import Message
from textual.widgets import TextArea


class ChatInput(TextArea):
    """Input panel for typing commands and messages."""

    class CommandSubmitted(Message):
        """Custom message posted when a command is submitted."""
        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_line_numbers = False
        self.soft_wrap = True

    async def _on_key(self, event) -> None:
        """Intercept keys to navigate and complete autocomplete suggestions if open."""
        try:
            autocomplete = self.app.query_one("#autocomplete-list")
        except Exception:
            autocomplete = None

        if autocomplete and autocomplete.styles.display == "block":
            if event.key == "up":
                event.prevent_default()
                event.stop()
                idx = autocomplete.highlighted
                if idx is not None and idx > 0:
                    autocomplete.highlighted = idx - 1
                elif idx is None and autocomplete.current_options:
                    autocomplete.highlighted = len(autocomplete.current_options) - 1
                return
            elif event.key == "down":
                event.prevent_default()
                event.stop()
                idx = autocomplete.highlighted
                if idx is not None and idx < len(autocomplete.current_options) - 1:
                    autocomplete.highlighted = idx + 1
                elif idx is None and autocomplete.current_options:
                    autocomplete.highlighted = 0
                return
            elif event.key == "tab":
                idx = autocomplete.highlighted if autocomplete.highlighted is not None else 0
                if idx is not None and 0 <= idx < len(autocomplete.current_options):
                    event.prevent_default()
                    event.stop()
                    self.complete_option(autocomplete, autocomplete.current_options[idx])
                    return
            elif event.key == "enter":
                idx = autocomplete.highlighted
                if idx is not None and 0 <= idx < len(autocomplete.current_options):
                    event.prevent_default()
                    event.stop()
                    self.complete_option(autocomplete, autocomplete.current_options[idx])
                    return
            elif event.key == "escape":
                event.prevent_default()
                event.stop()
                autocomplete.hide()
                return

        # 1. Allow Tab and Shift+Tab to switch focus between panels when autocomplete is NOT open
        if event.key in ("tab", "shift+tab"):
            return

        # 2. If autocomplete is not open, handle Enter (submit) vs newlines
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            command = self.text.strip()
            if command:
                self.post_message(self.CommandSubmitted(command))
            self.clear()
            return
        elif event.key in ("shift+enter", "ctrl+enter", "ctrl+j"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return

        await super()._on_key(event)

    def complete_option(self, autocomplete, option: str) -> None:
        """Complete the input value with the selected autocomplete option."""
        if autocomplete.show_type == "command":
            self.text = option + " "
            self.cursor_location = (0, len(self.text))
        elif autocomplete.show_type == "file":
            text = self.text
            new_text = re.sub(r"@([^\s]*)$", f"@{option}", text)
            self.text = new_text
            lines = new_text.split("\n")
            self.cursor_location = (len(lines) - 1, len(lines[-1]))
        autocomplete.hide()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle content changes to update the suggestions dropdown."""
        try:
            autocomplete = self.app.query_one("#autocomplete-list")
        except Exception:
            return

        if autocomplete:
            # Pass app's project_path or fallback to workspace root
            project_path = getattr(self.app, "planboard_path", None)
            if project_path:
                project_path = project_path.parent
            autocomplete.update_suggestions(event.text_area.text, project_path)
