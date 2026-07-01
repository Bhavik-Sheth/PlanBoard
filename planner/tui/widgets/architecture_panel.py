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
    can_focus = True

    BINDINGS = [
        ("c", "copy_content", "Copy Content"),
        ("ctrl+alt+c", "copy_content", "Copy Content"),
    ]

    def __init__(self, planner_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.planner_path = planner_path
        from planner.watcher.watcher_manager import WatcherManager
        self.watcher_manager = WatcherManager(str(planner_path))
        self._warning_shown = False

    def on_mount(self) -> None:
        self.refresh_diagram()
        self.poll_status()
        self.set_interval(5.0, self.poll_status)

    def poll_status(self) -> None:
        """Poll the watcher status and update the border title."""
        status = self.watcher_manager.get_status_for_tui()
        symbol = status["symbol"]
        color = status["color"]
        label = status["label"]

        from rich.text import Text
        self.border_title = Text.assemble(
            "Architecture  ",
            (symbol, color),
            f" {label}"
        )

        if label in ("Watcher crashed", "Unavailable"):
            if not self._warning_shown:
                self._warning_shown = True
                try:
                    viewer = self.app.query_one("#viewer-panel")
                    self.app.call_from_thread(
                        viewer.write_output,
                        "\n⚠️  [yellow]Architecture watcher stopped. Diagrams may be out of date.[/yellow]\n"
                        "    Type [bold]/diagram[/bold] to manually regenerate, or restart the app to resume live updates.\n"
                    )
                except Exception:
                    pass

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

    def action_copy_content(self) -> None:
        """Copy the active architecture diagram Markdown content to the system clipboard."""
        candidates = [
            self.planner_path / "ARCHITECTURE_DIAGRAMS" / "SystemArchitecture.md",
            self.planner_path / "ARCHITECTURE_DIAGRAMS" / "SystemDesign.md",
        ]
        text_to_copy = ""
        for candidate in candidates:
            if candidate.exists():
                try:
                    text_to_copy = candidate.read_text(encoding="utf-8")
                    break
                except Exception:
                    pass

        if not text_to_copy:
            text_to_copy = "No diagrams yet."

        try:
            self.app.copy_to_clipboard(text_to_copy)
            self.border_subtitle = "[Copied diagram to clipboard!]"
            self.set_timer(2.0, lambda: setattr(self, "border_subtitle", ""))
        except Exception as e:
            self.border_subtitle = f"[Copy failed: {e}]"
