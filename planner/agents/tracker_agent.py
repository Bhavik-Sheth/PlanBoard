"""
tracker_agent.py — Tracker agent. No LLM needed — purely reads disk state.
Reads: all PLANNER/*.md files (checks size/content)
Writes: Tracker.md
"""
from pathlib import Path
from datetime import datetime
from planner.state import PlannerState
from planner.files.writer import write_planner_file

# The canonical ordered list of planning files and their owning agents
TRACKED_FILES = [
    ("RawIdea.md",           "user input"),
    ("StructuredIdea.md",    "structuring_agent"),
    ("Constraints.md",       "user input"),
    ("PRD.md",               "prd_agent"),
    ("TRD.md",               "trd_agent"),
    ("Schema.md",            "schema_agent"),
    ("DesignDecisions.md",   "design_agent"),
    ("AppFlow.md",           "appflow_agent"),
    ("Rules.md",             "rules_agent"),
    ("ImplementationPlan.md","implementation_agent"),
]


def tracker_agent(state: PlannerState) -> PlannerState:
    """Scan all PLANNER files and write a human-readable Tracker.md status report."""
    planner_dir = Path(state.project_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows: list[str] = []
    rows.append(f"# Planner Tracker\n")
    rows.append(f"_Last updated: {now}_\n")
    rows.append("\n## Planning Files\n")
    rows.append("| File | Status | Approved |")
    rows.append("|------|--------|----------|")

    for filename, owner in TRACKED_FILES:
        path = planner_dir / filename
        exists = path.exists()
        non_empty = exists and path.stat().st_size > 0
        approved = filename in state.approved_files

        if not exists:
            status = "⬜ Missing"
        elif not non_empty:
            status = "⬜ Empty"
        else:
            status = "✅ Done"

        approved_mark = "✅" if approved else "—"
        rows.append(f"| {filename} | {status} | {approved_mark} |")

    # Modules section
    modules_dir = planner_dir / "MODULES"
    module_files = sorted(modules_dir.glob("*.md")) if modules_dir.exists() else []
    rows.append("\n## Modules\n")
    if module_files:
        rows.append("| Module | Status |")
        rows.append("|--------|--------|")
        for mf in module_files:
            non_empty = mf.stat().st_size > 0
            status = "✅ Done" if non_empty else "⬜ Empty"
            rows.append(f"| {mf.name} | {status} |")
    else:
        rows.append("_No modules defined yet. Use `planner module add <name>`._")

    # Known blockers
    rows.append("\n## Blockers / Notes\n")
    rows.append("_None recorded. Add blockers here manually if needed._\n")

    content = "\n".join(rows)
    write_planner_file(planner_dir / "Tracker.md", content, force=True)

    state.current_file = "Tracker.md"
    state.status = "drafting"
    # Route back to orchestrator to evaluate whether the pipeline is fully complete.
    # Do NOT route to "modules" here — modules are triggered explicitly by the user,
    # not as part of the main planning sequence.
    state.next_agent = "orchestrator"
    return state
