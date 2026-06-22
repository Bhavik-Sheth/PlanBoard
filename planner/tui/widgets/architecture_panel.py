"""
planner/tui/widgets/architecture_panel.py

ArchitecturePanel — top-right panel that renders SystemArchitecture.md
(or SystemDesign.md as fallback) from the ARCHITECTURE_DIAGRAMS/ directory
using rich.markdown.Markdown. Refreshes live when diagram files change.
"""

from pathlib import Path

from rich.text import Text
from textual.widgets import Static


_PLACEHOLDER = Text.assemble(
    ("⬡  Architecture Diagram Panel\n", "bold green"),
    ("─" * 42 + "\n", "dim green"),
    ("No diagrams yet. Run ", "dim"),
    ("/diagram", "bold cyan"),
    (" or ", "dim"),
    ("/run", "bold cyan"),
    (" to generate them.", "dim"),
)


class ArchitecturePanel(Static):
    """Top-right panel — displays SystemArchitecture.md (or SystemDesign.md) as rendered Markdown."""

    def __init__(self, planner_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.planner_path = planner_path

    def on_mount(self) -> None:
        self.refresh_diagram()

    def refresh_diagram(self, path: Path | None = None) -> None:
        """
        Load and display a Markdown architecture document from *path*.
        Falls back to SystemArchitecture.md, then SystemDesign.md.
        Shows a placeholder when no diagram content is available.
        """
        candidates = (
            [path] if path else [
                self.planner_path / "ARCHITECTURE_DIAGRAMS" / "SystemArchitecture.md",
                self.planner_path / "ARCHITECTURE_DIAGRAMS" / "SystemDesign.md",
            ]
        )

        for candidate in candidates:
            if candidate and candidate.exists():
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    from rich.markdown import Markdown
                    self.update(Markdown(content))
                    return

        self.update(_PLACEHOLDER)
