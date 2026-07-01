"""
planboard/main.py — Typer CLI entrypoint.

Commands:
  planboard init              → scaffold PLANBOARD/
  planboard describe <text>   → append to RawIdea.md + structure into StructuredIdea.md
  planboard run               → invoke the full LangGraph orchestration pipeline
  planboard status            → pretty-print Tracker.md
  planboard approve <file>    → mark file approved in Tracker.md
  planboard reset <file>      → clear + re-run one file's agent
  planboard module add <name> → plan a new module
  planboard module list       → list modules
  planboard consistency       → cross-file consistency check
  planboard finalize          → compile CLAUDE.md (planning done)
"""
import sys
from pathlib import Path
# pyrefly: ignore [missing-import]
import typer
from typing import Optional

app = typer.Typer(
    help="PlanBoard — AI-driven project planboard CLI.",
    no_args_is_help=False,
)

# Default PLANBOARD/ directory relative to cwd
def _planboard_dir() -> Path:
    return Path.cwd() / "PLANBOARD"


# ─────────────────────────────────────────────
# Default command: launch TUI (future phases)
# ─────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Launch the TUI when no subcommand is specified.
    """
    if ctx.invoked_subcommand is None:
        from planboard.tui.app import PlannerApp
        planboard_dir = _planboard_dir()
        tui_app = PlannerApp(planboard_path=planboard_dir)
        tui_app.run()



# ─────────────────────────────────────────────
# init
# ─────────────────────────────────────────────

@app.command(name="init")
def init_cmd() -> None:
    """Initialize PLANBOARD/ directory structure and run startup mode selection flow."""
    try:
        from planboard.agents.orchestrator import run_startup_flow
        from planboard.state import PlannerState
        state = PlannerState(project_path=str(_planboard_dir()))
        run_startup_flow(state)
    except Exception as e:
        typer.echo(f"[ERROR] {e}", err=True)
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# describe
# ─────────────────────────────────────────────

@app.command(name="describe")
def describe_cmd(text: str = typer.Argument(..., help="Your project idea text.")) -> None:
    """Append text to RawIdea.md and immediately structure it into StructuredIdea.md via LLM."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    # 1. Append to RawIdea.md
    from planboard.tools import append_file
    append_file(str(planboard_dir / "RawIdea.md"), text)
    typer.echo(f"✅  Appended to RawIdea.md ({len(text)} chars).")

    # Route to updates agent if planning is already underway
    prd_path = planboard_dir / "PRD.md"
    planning_underway = prd_path.exists() and prd_path.stat().st_size > 0
    if planning_underway:
        typer.echo("⏳  Planning is already underway. Routing to Updates Agent...")
        try:
            _run_update_loop(planboard_dir, text)
            return
        except Exception as e:
            typer.echo(f"[ERROR] Updates failed: {e}", err=True)
            raise typer.Exit(1)

    # 2. Run the structuring agent
    typer.echo("⏳  Structuring idea via LLM...")
    try:
        from planboard.state import PlannerState
        from planboard.agents.structuring_agent import structuring_agent
        state = PlannerState(project_path=str(planboard_dir))
        result = structuring_agent(state)
        if result.status == "needs_input":
            typer.echo(f"[INFO] {result.pending_questions[0]}")
        else:
            typer.echo("✅  StructuredIdea.md updated.")
    except Exception as e:
        typer.echo(f"[ERROR] Structuring failed: {e}", err=True)
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# update
# ─────────────────────────────────────────────

def _run_update_loop(planboard_dir: Path, text: str) -> None:
    from planboard.state import load_state
    from planboard.agents.orchestrator import OrchestratorAgent
    
    state = load_state(str(planboard_dir))
    orchestrator = OrchestratorAgent(state)
    
    # 1. Dispatch update analysis
    payload = orchestrator.handle_update(text)
    if payload.get("type") == "error":
        typer.echo(f"\n[INFO] {payload.get('message')}")
        return
        
    # Reload state in case it changed
    state = load_state(str(planboard_dir))
    orchestrator = OrchestratorAgent(state)
    
    # 2. Run execution loop if we have an active update plan
    while state.active_update_plan:
        run_payload = orchestrator.handle_run()
        
        if run_payload.get("type") == "file_complete":
            file = run_payload.get("file")
            summary = run_payload.get("summary", [])
            typer.echo(f"\n✅  {file} updated.")
            typer.echo("\nChanges made:")
            for bullet in summary:
                typer.echo(f"  • {bullet}")
                
            # Prompt user for approval or revision
            while True:
                try:
                    user_input = input(f"\nType /approve {file} to accept, or describe further changes:\n  ▶  ").strip()
                except (EOFError, KeyboardInterrupt):
                    typer.echo("\n[INTERRUPTED] Update aborted.")
                    orchestrator.handle_abort_update()
                    raise typer.Exit(1)
                    
                if user_input.startswith("/approve") or user_input.lower() in ("approve", "yes", "y"):
                    approve_payload = orchestrator.handle_approve(file)
                    break
                else:
                    typer.echo(f"🔄  Re-running {file} with feedback: {user_input}")
                    revise_payload = orchestrator.handle_revise(file, user_input)
                    if revise_payload.get("type") == "file_complete":
                        file = revise_payload.get("file")
                        summary = revise_payload.get("summary", [])
                        typer.echo(f"\n✅  {file} updated with feedback.")
                        typer.echo("\nChanges made:")
                        for bullet in summary:
                            typer.echo(f"  • {bullet}")
        elif run_payload.get("type") == "update_complete":
            files_changed = run_payload.get("files_changed", [])
            stale_warning = run_payload.get("stale_warning", "")
            if files_changed:
                typer.echo(f"\n✅  Update applied. Files changed: {', '.join(files_changed)}")
            else:
                typer.echo("\n✅  Update completed.")
            if stale_warning:
                typer.echo(f"⚠️  {stale_warning}")
            break
        elif run_payload.get("type") == "error":
            typer.echo(f"\n[ERROR] Update failed: {run_payload.get('message')}", err=True)
            raise typer.Exit(1)
        else:
            break
            
        # Reload state in loop
        state = load_state(str(planboard_dir))
        orchestrator = OrchestratorAgent(state)


@app.command(name="update")
def update_cmd(
    text: Optional[str] = typer.Argument(None, help="The description of the change.")
) -> None:
    """Apply a change/update to the project design and planning files."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    # Check if planning files exist yet
    si_path = planboard_dir / "StructuredIdea.md"
    if not si_path.exists() or si_path.stat().st_size == 0:
        typer.echo("[ERROR] No planning session found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    if not text:
        try:
            text = input("What changed? Describe the update: ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nAborted.")
            raise typer.Exit(1)
        if not text:
            typer.echo("[ERROR] Update description cannot be empty.", err=True)
            raise typer.Exit(1)

    try:
        _run_update_loop(planboard_dir, text)
    except KeyboardInterrupt:
        typer.echo("\n[INTERRUPTED] Update aborted by user.")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"\n[ERROR] {e}", err=True)
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# run
# ─────────────────────────────────────────────

@app.command(name="run")
def run_cmd() -> None:
    """Run the full LangGraph orchestration pipeline (fills all planning docs)."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    typer.echo("🚀  Starting planboard run...\n")
    try:
        from planboard.graph import run_graph
        final_state = run_graph(str(planboard_dir))
        if final_state.status == "done":
            typer.echo("\n✅  Planning run complete. Run `planboard status` to review.")
        elif final_state.status == "error":
            typer.echo(f"\n[ERROR] Run stopped: {final_state.error_message}", err=True)
            raise typer.Exit(1)
    except KeyboardInterrupt:
        typer.echo("\n[INTERRUPTED] Run aborted by user.")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"\n[ERROR] {e}", err=True)
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# status
# ─────────────────────────────────────────────

@app.command(name="status")
def status_cmd() -> None:
    """Show the current status from Tracker.md."""
    planboard_dir = _planboard_dir()
    tracker_path = planboard_dir / "Tracker.md"
    if not tracker_path.exists():
        typer.echo("Tracker.md not found. Run `planboard run` first.")
        return
    typer.echo(tracker_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────
# approve
# ─────────────────────────────────────────────

@app.command(name="approve")
def approve_cmd(file: str = typer.Argument(..., help="Filename to approve, e.g. PRD.md")) -> None:
    """Mark a planning file as approved in Tracker.md."""
    planboard_dir = _planboard_dir()
    from planboard.utils import resolve_relative_path
    resolved = resolve_relative_path(planboard_dir, file)
    if resolved:
        file = resolved
    target = planboard_dir / file
    if not target.exists():
        typer.echo(f"[ERROR] {file} not found in PLANBOARD/.", err=True)
        raise typer.Exit(1)

    # Call update_file_status directly
    from planboard.tools import update_file_status
    project_root = str(planboard_dir.parent)
    update_file_status(project_root, file, "✅ Approved", "user")
    typer.echo(f"✅  {file} marked as approved.")


# ─────────────────────────────────────────────
# reset
# ─────────────────────────────────────────────

@app.command(name="reset")
def reset_cmd(file: str = typer.Argument(..., help="Filename to reset and re-run, e.g. PRD.md")) -> None:
    """Clear a planning file and re-run its agent (requires confirmation)."""
    planboard_dir = _planboard_dir()
    from planboard.utils import resolve_relative_path, resolve_agent
    resolved = resolve_relative_path(planboard_dir, file)
    if resolved:
        file = resolved
    target = planboard_dir / file

    if not target.exists():
        typer.echo(f"[ERROR] {file} not found in PLANBOARD/.", err=True)
        raise typer.Exit(1)

    confirmed = typer.confirm(f"Clear {file} and re-run its agent?", default=False)
    if not confirmed:
        typer.echo("Aborted.")
        return

    # Clear the file
    target.write_text("", encoding="utf-8")
    typer.echo(f"🗑  {file} cleared.")

    # Re-run the appropriate agent
    agent_name = resolve_agent(file)

    if not agent_name:
        typer.echo(f"[WARN] No agent known for {file}. File cleared but not re-run.")
        return

    typer.echo(f"⏳  Re-running {agent_name} agent...")
    _run_single_agent(str(planboard_dir), agent_name, file)
    typer.echo(f"✅  {file} regenerated.")


def _run_single_agent(planboard_path: str, agent_name: str, filename: Optional[str] = None) -> None:
    """Import and invoke a single agent by name using the centralized registry."""
    from planboard.state import PlannerState
    from planboard.tools import read_file
    from planboard.agents.orchestrator import _get_agent_fn

    if agent_name == "diagram":
        from planboard.agents.architecture_diagram_agent import generate_diagrams
        generate_diagrams(planboard_path)
        return

    planboard_dir = Path(planboard_path)
    si_path = planboard_dir / "StructuredIdea.md"
    structured_idea = read_file(str(si_path)).strip() if si_path.exists() else ""
    state = PlannerState(project_path=planboard_path, structured_idea=structured_idea)

    if agent_name == "modules" and filename:
        module_name = filename.split("/")[-1].replace(".md", "")
        state.context_files["__module_name__"] = module_name

    fn = _get_agent_fn(agent_name)
    fn(state)


# ─────────────────────────────────────────────
# module subcommands
# ─────────────────────────────────────────────

module_app = typer.Typer(help="Manage planboard modules.")
app.add_typer(module_app, name="module")


@module_app.command(name="add")
def module_add_cmd(name: str = typer.Argument(..., help="Module name (no spaces, no .md)")) -> None:
    """Create and generate a spec for a new module."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    from planboard.state import PlannerState
    from planboard.agents.module_planboard_agent import module_planboard_agent
    from planboard.tools import read_file

    si_path = planboard_dir / "StructuredIdea.md"
    structured_idea = read_file(str(si_path)).strip() if si_path.exists() else ""

    state = PlannerState(
        project_path=str(planboard_dir),
        structured_idea=structured_idea,
        context_files={"__module_name__": name},
    )
    typer.echo(f"⏳  Generating spec for module '{name}'...")
    module_planboard_agent(state)
    typer.echo(f"✅  MODULES/{name}.md created.")


@module_app.command(name="list")
def module_list_cmd() -> None:
    """List all modules in PLANBOARD/MODULES/."""
    modules_dir = _planboard_dir() / "MODULES"
    if not modules_dir.exists():
        typer.echo("No MODULES/ directory found.")
        return
    files = sorted(modules_dir.glob("*.md"))
    if not files:
        typer.echo("No modules defined yet. Use `planboard module add <name>`.")
        return
    for f in files:
        size = f.stat().st_size
        status = "✅" if size > 0 else "⬜"
        typer.echo(f"  {status}  {f.name}")


# ─────────────────────────────────────────────
# consistency
# ─────────────────────────────────────────────

@app.command(name="consistency")
def consistency_cmd() -> None:
    """Run a read-only cross-file consistency check and print the report."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    from planboard.state import PlannerState
    from planboard.agents.orchestrator import run_consistency_check

    state = PlannerState(project_path=str(planboard_dir))
    typer.echo("🔍  Running consistency check...\n")
    report = run_consistency_check(state)
    typer.echo(report)



# ─────────────────────────────────────────────
# diagram
# ─────────────────────────────────────────────

@app.command(name="diagram")
def diagram_cmd() -> None:
    """Manually regenerate architecture diagrams from TRD.md, Schema.md, and AppFlow.md."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    typer.echo("⏳  Regenerating architecture diagrams...")
    try:
        from planboard.agents.architecture_diagram_agent import generate_diagrams
        generate_diagrams(str(planboard_dir))
        typer.echo("✅  Architecture diagrams regenerated.")
    except Exception as e:
        typer.echo(f"[ERROR] Diagram generation failed: {e}", err=True)
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# finalize (compile CLAUDE.md)
# ─────────────────────────────────────────────

@app.command(name="finalize")
def finalize_cmd() -> None:
    """Compile CLAUDE.md from all approved planning docs (ends the planning phase)."""
    planboard_dir = _planboard_dir()
    if not planboard_dir.exists():
        typer.echo("[ERROR] PLANBOARD/ not found. Run `planboard init` first.", err=True)
        raise typer.Exit(1)

    confirmed = typer.confirm(
        "This will compile CLAUDE.md and signal that planning is complete. Continue?",
        default=False,
    )
    if not confirmed:
        typer.echo("Aborted.")
        return

    typer.echo("⏳  Compiling CLAUDE.md...")
    _compile_claude_md(str(planboard_dir))
    typer.echo("✅  CLAUDE.md written to project root. Planning phase complete.")


def _compile_claude_md(planboard_path: str) -> None:
    """Compile CLAUDE.md via FinalizerAgent (LLM-powered summarization)."""
    from planboard.agents.finalizer_agent import finalizer_agent
    from planboard.tools import write_file

    planboard_dir = Path(planboard_path)
    project_root = planboard_dir.parent

    # Load all PLANBOARD/ file contents
    files = {}
    source_files = [
        "StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md",
        "Schema.md", "DesignDecisions.md", "AppFlow.md", "Rules.md",
        "ImplementationPlan.md",
    ]
    for fname in source_files:
        fpath = planboard_dir / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            files[fname] = fpath.read_text(encoding="utf-8").strip()

    # Also include MODULES/
    modules_dir = planboard_dir / "MODULES"
    if modules_dir.exists():
        for mf in sorted(modules_dir.glob("*.md")):
            content = mf.read_text(encoding="utf-8").strip()
            if content:
                files[f"MODULES/{mf.name}"] = content

    result = finalizer_agent(files)

    claude_path = project_root / "CLAUDE.md"
    write_file(str(claude_path), result["claude_md_content"], overwrite=True)

    if result.get("warnings"):
        for w in result["warnings"]:
            typer.echo(f"  ⚠️  {w}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app()
