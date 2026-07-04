"""
planboard/tui/app.py

PlannerApp — the main Textual App class that ties the panels together,
defines keyboard bindings, and routes events to the backend agents/commands.
"""

import builtins
import contextlib
import queue
import sys
import threading
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree

from planboard.tui.widgets.architecture_panel import ArchitecturePanel
from planboard.tui.widgets.chat_input import ChatInput
from planboard.tui.widgets.file_tree import PlannerFileTree
from planboard.tui.widgets.viewer_panel import ViewerPanel
from planboard.tui.widgets.autocomplete import AutocompleteList


from planboard.utils import resolve_relative_path, resolve_agent


class PlannerApp(App):
    """The main TUI Application for PlanBoard."""

    CSS_PATH = "planboard.css"
    TITLE = "PlanBoard"
    SUB_TITLE = "AI-driven project planboard"

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("escape", "focus_chat", "Focus Chat"),
        ("ctrl+e", "toggle_architecture", "Expand/Collapse Architecture"),
        ("f2", "toggle_architecture", "Expand/Collapse Architecture"),
        ("ctrl+t", "toggle_viewer_mode", "Toggle Edit/Preview"),
    ]

    def __init__(self, planboard_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.planboard_path = planboard_path or (Path.cwd() / "PLANBOARD")
        self.input_queue = queue.Queue()
        # Fix 10: use threading.Event instead of a plain bool for thread-safe
        # cross-thread signaling between the Textual main thread and worker threads.
        self._input_event = threading.Event()
        self.current_selected_file = None
        self.chat_history = []
        import sys
        self._is_test = "pytest" in sys.modules

    def get_selected_relative_path(self) -> str:
        """Return the selected file path relative to the planboard directory."""
        if not self.current_selected_file:
            return ""
        try:
            return str(self.current_selected_file.relative_to(self.planboard_path))
        except ValueError:
            return self.current_selected_file.name

    def compose(self) -> ComposeResult:
        # Determine the directory path to display.
        # If the planboard_path doesn't exist, show current directory as fallback.
        tree_path = self.planboard_path if self.planboard_path.exists() else Path.cwd()

        with Horizontal():
            yield PlannerFileTree(tree_path, id="file-tree")
            with Vertical(id="right-pane"):
                yield ArchitecturePanel(self.planboard_path, id="architecture-panel")
                yield ViewerPanel(id="viewer-panel")
                yield AutocompleteList(id="autocomplete-list")
                yield ChatInput(id="chat-input", placeholder="Type /command or chat message...")

    def on_mount(self) -> None:
        # Set panel titles
        self.viewer = self.query_one("#viewer-panel")
        self.file_tree = self.query_one("#file-tree")
        self.architecture_panel = self.query_one("#architecture-panel")
        self.chat_input = self.query_one("#chat-input")

        self.file_tree.border_title = "FILE VIEW"
        self.architecture_panel.border_title = "ARCHITECTURE PANEL"
        self.architecture_panel.border_subtitle = "Ctrl+E or F2 to Maximize"
        self.viewer.border_title = "RESPONSE / VIEWER PANEL"
        self.chat_input.border_title = "CHAT INPUT"

        # Auto-focus the chat input on launch
        self.chat_input.focus()

        # Instantiate ExecutiveAgent
        from planboard.agents.executive_agent import ExecutiveAgent
        from planboard.state import load_state
        self.state = load_state(str(self.planboard_path))
        self.executive = ExecutiveAgent(self.state)

        # Print welcome/warning messages in ViewerPanel and run startup flow
        viewer = self.query_one("#viewer-panel")
        
        def startup_worker():
            rendered = self.executive.handle_startup()
            self.call_from_thread(
                viewer.write_output,
                f"🤖 **PlanBoard:**\n{rendered}\n"
            )

        if not self._is_test:
            self.run_in_background(startup_worker)

        # Start directory/architecture watcher
        self.start_watcher()

    def on_unmount(self) -> None:
        """Clean up background processes when the application exits."""
        from planboard.watcher.watcher_manager import WatcherManager
        wm = WatcherManager(str(self.planboard_path))
        wm.stop()

    def start_watcher(self) -> None:
        """Spawn a background thread to watch for file system changes and refresh UI."""
        from watchfiles import watch
        import threading

        def watch_loop():
            try:
                # Watch the parent directory (project root) to handle non-existence of PLANBOARD/
                for changes in watch(self.planboard_path.parent):
                    if not self.is_running:
                        break

                    # Check for updates in PLANBOARD/
                    has_planboard_change = any(
                        Path(path).is_relative_to(self.planboard_path)
                        for _, path in changes
                    )

                    if has_planboard_change:
                        # Reload the file tree
                        self.call_from_thread(self.query_one("#file-tree").reload)

                        # If architecture diagrams changed, refresh architecture panel
                        has_arch_change = any(
                            Path(path).is_relative_to(self.planboard_path / "ARCHITECTURE_DIAGRAMS")
                            for _, path in changes
                        )
                        if has_arch_change:
                            self.call_from_thread(self.query_one("#architecture-panel").refresh_diagram)
            except Exception:
                pass

        t = threading.Thread(target=watch_loop, daemon=True)
        t.start()

    def run_in_background(self, func, *args, **kwargs) -> None:
        """Run a function in a background worker thread, redirecting stdout/stderr to TUI."""
        def worker():
            viewer = self.query_one("#viewer-panel")

            # Helper to write to viewer thread-safely
            def write_to_viewer(text: str):
                self.call_from_thread(viewer.write_output, text)

            class ThreadSafeStream:
                """Buffers stdout/stderr output and flushes to the viewer in line-sized chunks."""
                def __init__(self, callback):
                    self.callback = callback
                    self.buffer = ""

                def write(self, data):
                    self.buffer += data
                    # Flush whenever we have a complete paragraph (blank line) or enough content
                    while "\n" in self.buffer:
                        line, self.buffer = self.buffer.split("\n", 1)
                        # Strip any residual Rich markup tags before passing to Markdown
                        self.callback(line)
                    return len(data)

                def flush(self):
                    if self.buffer:
                        self.callback(self.buffer)
                        self.buffer = ""

            # Save original input and patch
            original_input = builtins.input

            def tui_input(prompt=""):
                if prompt:
                    sys.stdout.write(prompt)
                    sys.stdout.flush()

                # Hide thinking indicator while waiting for input
                self.call_from_thread(viewer.show_thinking, False)

                # Signal that we are waiting for user input
                self._input_event.set()

                # Retrieve from queue (blocks until user submits response)
                ans = self.input_queue.get()

                # Show thinking indicator again as worker resumes
                self.call_from_thread(viewer.show_thinking, True)

                if ans == "/abort":
                    raise KeyboardInterrupt("Action aborted by user.")
                return ans

            builtins.input = tui_input
            stream = ThreadSafeStream(write_to_viewer)

            # Show thinking indicator when starting the worker
            self.call_from_thread(viewer.show_thinking, True)

            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                try:
                    func(*args, **kwargs)
                except KeyboardInterrupt:
                    write_to_viewer("\n> ⚠️ Operation cancelled/aborted.")
                except Exception as e:
                    write_to_viewer(f"\n> ❌ Error: {e}")
                finally:
                    builtins.input = original_input
                    self._input_event.clear()
                    # Hide thinking indicator when finished
                    self.call_from_thread(viewer.show_thinking, False)

        self.run_worker(worker, thread=True)

    def action_focus_chat(self) -> None:
        """Focus the Chat Input panel."""
        self.query_one("#chat-input").focus()

    def action_toggle_viewer_mode(self) -> None:
        """Toggle between preview and edit mode for Markdown files in the ViewerPanel."""
        self.query_one("#viewer-panel").action_toggle_mode()

    def action_toggle_architecture(self) -> None:
        """Toggle the architecture panel expansion."""
        arch_panel = self.query_one("#architecture-panel")
        viewer_panel = self.query_one("#viewer-panel")
        chat_input = self.query_one("#chat-input")
        
        is_expanding = not arch_panel.has_class("expanded")
        
        arch_panel.toggle_class("expanded")
        viewer_panel.toggle_class("collapsed")
        chat_input.toggle_class("collapsed")
        
        if is_expanding:
            arch_panel.border_title = "ARCHITECTURE PANEL (MAXIMIZED)"
            arch_panel.border_subtitle = "Ctrl+E or F2 to Minimize"
            arch_panel.focus()
        else:
            arch_panel.border_title = "ARCHITECTURE PANEL"
            arch_panel.border_subtitle = "Ctrl+E or F2 to Maximize"
            chat_input.focus()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection from the file tree, opening the file in the Viewer Panel."""
        self.current_selected_file = event.path
        viewer = self.query_one("#viewer-panel")
        viewer.show_file(event.path)

    def on_option_list_option_selected(self, event) -> None:
        """Handle clicks/selection on autocomplete options."""
        try:
            autocomplete = self.query_one("#autocomplete-list")
        except Exception:
            return

        if autocomplete and autocomplete.styles.display == "block":
            chat_input = self.query_one("#chat-input")
            chat_input.complete_option(autocomplete, event.option.id)
            chat_input.focus()

    def on_chat_input_command_submitted(self, event: ChatInput.CommandSubmitted) -> None:
        """Process chat input submissions via ExecutiveAgent."""
        cmd = event.command.strip()
        if not cmd:
            return

        # 1. If we are waiting for grilling/confirmation input (legacy/fallback)
        if self._input_event.is_set():
            self._input_event.clear()
            self.viewer.write_output(f"👤 **You:** {cmd}\n")
            self.input_queue.put(cmd)
            return

        # 2. Process using ExecutiveAgent in a background thread
        # Capture the currently open file for context-aware intent classification
        active_file = self.get_selected_relative_path()

        def run_cmd():
            # Add a separator and prune old lines before each new command.
            # This is the key TUI lag fix: old content is dropped from the
            # render window so markdown re-parsing stays fast.
            self.call_from_thread(self.viewer.start_new_command)

            # Print user message to viewer immediately
            self.call_from_thread(
                self.viewer.write_output,
                f"👤 **You:** {cmd}\n"
            )

            parsed_cmd, rendered_output = self.executive.process(cmd, active_file=active_file)

            # Print assistant response thread-safely to viewer
            self.call_from_thread(
                self.viewer.write_output,
                f"🤖 **PlanBoard:**\n{rendered_output}\n"
            )

            # Reload UI tree/diagram after any command that creates or modifies files
            if parsed_cmd:
                cmd_type = parsed_cmd.get("command")
                file_writing_cmds = {
                    "init", "describe", "run", "reset", "reset_confirmed",
                    "edit", "approve", "revise", "module_add", "update_confirmed",
                }
                if cmd_type in file_writing_cmds:
                    self.call_from_thread(self.file_tree.reload)
                if cmd_type in ("diagram",):
                    self.call_from_thread(self.architecture_panel.refresh_diagram)

        self.run_in_background(run_cmd)
