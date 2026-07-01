"""
planner/tui/widgets/file_tree.py

PlannerFileTree — a DirectoryTree that:
- Filters out hidden files, __pycache__, .venv, etc.
- Styled for the PlannerX dark theme.
"""

from pathlib import Path
from typing import Iterable

from textual.widgets import DirectoryTree


class PlannerFileTree(DirectoryTree):
    """File tree panel showing the PLANNER/ directory structure."""

    BINDINGS = [
        ("c", "copy_content", "Copy Content"),
        ("ctrl+alt+c", "copy_content", "Copy Content"),
    ]

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Exclude hidden files and Python caches."""
        skip = {
            "__pycache__",
            ".venv",
            ".git",
            ".pytest_cache",
            "plannerx.egg-info",
            "uv.lock",
        }
        return [
            p for p in paths
            if not p.name.startswith(".")
            and p.name not in skip
        ]

    def action_copy_content(self) -> None:
        """Copy the path of the currently highlighted file to the system clipboard."""
        node = self.cursor_node
        if node and node.data:
            path = getattr(node.data, "path", None)
            if path:
                try:
                    self.app.copy_to_clipboard(str(path))
                    self.border_subtitle = f"[Copied path: {path.name}]"
                    self.set_timer(2.0, lambda: setattr(self, "border_subtitle", ""))
                except Exception as e:
                    self.border_subtitle = f"[Copy failed: {e}]"
