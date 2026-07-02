"""
planboard/tui/widgets/viewer_panel.py

ViewerPanel — mid-right panel that renders either live agent Markdown output
or file content (editable/preview) when a file is selected in the directory tree.

Output mode: accumulates raw markdown text lines and renders a rolling window
(last _MAX_RENDER_LINES lines) to prevent lag from re-rendering huge buffers.
File mode: shows markdown files in preview by default; Ctrl+T toggles to editor.
"""

from collections import deque
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import TextArea, Markdown, Label

# Maximum number of lines rendered in the markdown widget at once.
# Older lines are kept in output_buffer for copy but dropped from the render.
_MAX_RENDER_LINES = 300


class ViewerPanel(Vertical):
    """Viewer panel for displaying agent output as rendered Markdown, or file contents."""

    BINDINGS = [
        ("c", "copy_content", "Copy Content"),
        ("ctrl+alt+c", "copy_content", "Copy Content"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.mode = "output"
        self.active_file_path = None
        self._loading_file = False
        self.is_preview_mode = True
        self.thinking = None
        self.markdown_widget = None
        # Rolling list of raw markdown lines for rendering (capped at _MAX_RENDER_LINES)
        self._output_lines: list[str] = []
        # Full history buffer for copy support (unlimited, bounded by deque maxlen)
        self.output_buffer: deque[str] = deque(maxlen=500)

    def compose(self) -> ComposeResult:
        yield Markdown(id="viewer-markdown")
        yield TextArea(id="viewer-text-area")
        yield Label("⚙ Thinking...", id="viewer-thinking")

    def on_mount(self) -> None:
        self.markdown_widget = self.query_one("#viewer-markdown", Markdown)
        self.text_area = self.query_one("#viewer-text-area", TextArea)
        self.thinking = self.query_one("#viewer-thinking", Label)
        # Start in output mode — Markdown widget is visible, TextArea hidden
        self.text_area.display = False
        self.text_area.show_line_numbers = True
        self.text_area.soft_wrap = True
        self.thinking.display = False

    def on_unmount(self) -> None:
        """Ensure any pending changes are saved when the widget is unmounted."""
        self.save_current_file()

    def save_current_file(self) -> None:
        """Save the current text area content to the active file."""
        if self.mode == "file" and self.active_file_path:
            try:
                current_text = self.text_area.text
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

    # -------------------------------------------------------------------------
    # Output mode (agent responses rendered as Markdown)
    # -------------------------------------------------------------------------

    def start_new_command(self) -> None:
        """
        Call at the start of a new command to add a visual separator between
        command outputs and prune old lines so the render stays fast.
        Kept in output mode; does NOT clear history from output_buffer.
        """
        if self._output_lines:
            # Add a horizontal rule separator between commands
            separator = "\n---\n"
            self._output_lines.append(separator)
            self.output_buffer.append(separator)
            # Keep only the last _MAX_RENDER_LINES to prevent lag
            if len(self._output_lines) > _MAX_RENDER_LINES:
                self._output_lines = self._output_lines[-_MAX_RENDER_LINES:]

    def write_output(self, text: str) -> None:
        """
        Append agent output text to the rolling window and re-render.
        Only the last _MAX_RENDER_LINES lines are rendered to prevent TUI lag
        from re-parsing an ever-growing markdown string.
        Switches back to output mode if currently viewing a file.
        """
        self.save_current_file()
        self.active_file_path = None

        # Track full history for copy
        self.output_buffer.append(text)

        # Add to rolling render lines
        self._output_lines.append(text)

        # Enforce rolling window cap
        if len(self._output_lines) > _MAX_RENDER_LINES:
            self._output_lines = self._output_lines[-_MAX_RENDER_LINES:]

        if self.mode != "output":
            self.mode = "output"
            self.text_area.display = False
            self.markdown_widget.display = True
            self.border_subtitle = ""

        # Render only the rolling window — this is the performance fix
        self.markdown_widget.update("\n".join(self._output_lines))

    def clear_output(self) -> None:
        """Clear the output buffer and reset the markdown view."""
        self.save_current_file()
        self.output_buffer.clear()
        self._output_lines = []
        self.mode = "output"
        self.active_file_path = None
        self.text_area.display = False
        self.markdown_widget.display = True
        self.markdown_widget.update("")

    # -------------------------------------------------------------------------
    # File mode (open from file tree)
    # -------------------------------------------------------------------------

    def show_file(self, path: Path) -> None:
        """Switch to file mode and render the file content."""
        self.save_current_file()

        self.mode = "file"
        self.active_file_path = path

        if not path.exists():
            self.markdown_widget.display = False
            self.text_area.display = True
            self._loading_file = True
            self.text_area.text = f"Error: File {path} does not exist."
            self._loading_file = False
            return

        try:
            content = path.read_text(encoding="utf-8")
            self._loading_file = True
            self.text_area.text = content
            self._loading_file = False

            if path.suffix.lower() in (".md", ".markdown") and self.is_preview_mode:
                self.text_area.display = False
                self.markdown_widget.display = True
                self.markdown_widget.update(content)
                self.border_subtitle = "[Previewing — Ctrl+T to edit]"
            else:
                self.markdown_widget.display = False
                self.text_area.display = True
                self.text_area.focus()
                if path.suffix.lower() in (".md", ".markdown"):
                    self.border_subtitle = "[Editing — Ctrl+T to preview]"
                else:
                    self.border_subtitle = ""
        except Exception as e:
            self._loading_file = True
            self.text_area.text = f"Error reading file {path.name}: {e}"
            self._loading_file = False

    def action_toggle_mode(self) -> None:
        """Toggle between preview and edit mode for Markdown files (called from app.py)."""
        if self.mode == "file" and self.active_file_path:
            suffix = self.active_file_path.suffix.lower()
            if suffix in (".md", ".markdown"):
                self.is_preview_mode = not self.is_preview_mode
                if self.is_preview_mode:
                    self.save_current_file()
                    self.text_area.display = False
                    self.markdown_widget.display = True
                    try:
                        content = self.active_file_path.read_text(encoding="utf-8")
                        self.markdown_widget.update(content)
                    except Exception:
                        pass
                    self.border_subtitle = "[Previewing — Ctrl+T to edit]"
                else:
                    self.markdown_widget.display = False
                    self.text_area.display = True
                    self.text_area.focus()
                    self.border_subtitle = "[Editing — Ctrl+T to preview]"
        elif self.mode == "output":
            # In output mode, Ctrl+T scrolls to top / refreshes the view
            self.markdown_widget.scroll_home()

    # -------------------------------------------------------------------------
    # Thinking indicator
    # -------------------------------------------------------------------------

    def show_thinking(self, show: bool) -> None:
        """Show or hide the golden yellow thinking/processing indicator."""
        if self.thinking is not None:
            self.thinking.display = show

    # -------------------------------------------------------------------------
    # Copy content
    # -------------------------------------------------------------------------

    def action_copy_content(self) -> None:
        """Copy the current file or agent output content to the system clipboard."""
        text_to_copy = ""
        if self.mode == "file":
            if self.active_file_path and self.active_file_path.exists():
                try:
                    text_to_copy = self.active_file_path.read_text(encoding="utf-8")
                except Exception:
                    text_to_copy = self.text_area.text
            else:
                text_to_copy = self.text_area.text
        else:
            # Return raw accumulated markdown (strip any rich markup from output_buffer)
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
                old_subtitle = self.border_subtitle
                self.border_subtitle = "[Copied content to clipboard!]"
                self.set_timer(2.0, lambda: setattr(self, "border_subtitle", old_subtitle))
            except Exception as e:
                self.border_subtitle = f"[Copy failed: {e}]"
