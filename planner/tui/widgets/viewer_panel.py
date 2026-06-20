"""
planner/tui/widgets/viewer_panel.py

ViewerPanel — mid-right panel that renders either live agent text logs
or file content when a file is selected in the directory tree.
"""

from pathlib import Path
from rich.markdown import Markdown
from textual.widgets import RichLog


class ViewerPanel(RichLog):
    """Viewer panel for displaying logs or Markdown file contents."""

    def __init__(self, **kwargs) -> None:
        # Enable markup support by default and wrap lines
        kwargs.setdefault("markup", True)
        kwargs.setdefault("wrap", True)
        super().__init__(**kwargs)
        self.mode = "output"
        self.output_buffer = []

    def write_output(self, text: str) -> None:
        """Append a log line in output mode, switching back to output mode if in file mode."""
        self.output_buffer.append(text)
        if self.mode != "output":
            self.mode = "output"
            self.clear()
            for line in self.output_buffer:
                self.write(line)
        else:
            self.write(text)

    def show_file(self, path: Path) -> None:
        """Switch to file mode and render the file content (Markdown/Mermaid)."""
        self.mode = "file"
        self.clear()
        if not path.exists():
            self.write(f"[red]Error: File {path} does not exist.[/red]")
            return

        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix == ".mmd":
                from planner.utils.mermaid_render import render_mermaid_text
                self.write(render_mermaid_text(content))
            else:
                self.write(Markdown(content))
        except Exception as e:
            self.write(f"[red]Error reading file {path.name}: {e}[/red]")

    def clear_output(self) -> None:
        """Clear the output buffer and switch back to empty output mode."""
        self.output_buffer.clear()
        self.mode = "output"
        self.clear()
