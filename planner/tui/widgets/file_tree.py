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
