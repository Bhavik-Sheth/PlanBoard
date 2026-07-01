"""
planner/tui/widgets/viewer_panel.py

ViewerPanel — mid-right panel that renders either live agent text logs
or file content (editable) when a file is selected in the directory tree.
"""

from collections import deque
from pathlib import Path
from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, TextArea


class ViewerPanel(Vertical):
    """Viewer panel for displaying logs or Markdown/text file contents."""

    BINDINGS = [
        ("c", "copy_content", "Copy Content"),
        ("ctrl+alt+c", "copy_content", "Copy Content"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.mode = "output"
        self.active_file_path = None
        self._loading_file = False
        # Use a bounded deque to prevent unbounded memory growth in long sessions.
        self.output_buffer: deque[str] = deque(maxlen=500)

    def compose(self) -> ComposeResult:
        yield RichLog(id="viewer-log", markup=True, wrap=True)
        yield TextArea(id="viewer-text-area")

    def on_mount(self) -> None:
        self.rich_log = self.query_one("#viewer-log", RichLog)
        self.text_area = self.query_one("#viewer-text-area", TextArea)
        self.text_area.display = False  # Start in output (log) mode
        self.text_area.show_line_numbers = True
        self.text_area.soft_wrap = True

    def on_unmount(self) -> None:
        """Ensure any pending changes are saved when the widget is unmounted."""
        self.save_current_file()

    def save_current_file(self) -> None:
        """Save the current text area content to the active file."""
        if self.mode == "file" and self.active_file_path:
            try:
                # Get current content from the text area
                current_text = self.text_area.text
                # Only write if the file content actually changed
                if self.active_file_path.exists():
                    existing_text = self.active_file_path.read_text(encoding="utf-8")
                    if existing_text == current_text:
                        return
                self.active_file_path.write_text(current_text, encoding="utf-8")
            except Exception:
                pass

    def on_text_area_blur(self, event) -> None:
        """Autosave when the edit text area loses focus."""
        self.save_current_file()

    def write_output(self, text: str) -> None:
        """Append a log line in output mode, switching back to output mode if in file mode."""
        self.save_current_file()
        self.active_file_path = None
        self.output_buffer.append(text)
        if self.mode != "output":
            self.mode = "output"
            self.rich_log.display = True
            self.text_area.display = False
            self.rich_log.clear()
            for line in self.output_buffer:
                self.rich_log.write(line)
        else:
            self.rich_log.write(text)

    def show_file(self, path: Path) -> None:
        """Switch to file mode and render the file content (editable)."""
        # Save any edits on the previously opened file first
        self.save_current_file()

        self.mode = "file"
        self.active_file_path = path
        self.rich_log.display = False
        self.text_area.display = True
        self.text_area.focus()

        if not path.exists():
            self._loading_file = True
            self.text_area.text = f"Error: File {path} does not exist."
            self._loading_file = False
            return

        try:
            content = path.read_text(encoding="utf-8")
            self._loading_file = True
            self.text_area.text = content
            self._loading_file = False
        except Exception as e:
            self._loading_file = True
            self.text_area.text = f"Error reading file {path.name}: {e}"
            self._loading_file = False

    def clear_output(self) -> None:
        """Clear the output buffer and switch back to empty output mode."""
        self.save_current_file()
        self.output_buffer.clear()
        self.mode = "output"
        self.active_file_path = None
        self.rich_log.display = True
        self.text_area.display = False
        self.rich_log.clear()

    def action_copy_content(self) -> None:
        """Copy the current file or log output content to the system clipboard."""
        text_to_copy = ""
        if self.mode == "file":
            text_to_copy = self.text_area.text
        else:
            from rich.text import Text
            clean_lines = []
            for line in self.output_buffer:
                try:
                    clean_lines.append(Text.from_markup(line).plain)
                except Exception:
                    clean_lines.append(str(line))
            text_to_copy = "\n".join(clean_lines)

        if text_to_copy:
            try:
                self.app.copy_to_clipboard(text_to_copy)
                self.border_subtitle = "[Copied content to clipboard!]"
                self.set_timer(2.0, lambda: setattr(self, "border_subtitle", ""))
            except Exception as e:
                self.border_subtitle = f"[Copy failed: {e}]"

