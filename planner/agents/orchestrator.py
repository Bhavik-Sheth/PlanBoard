"""
orchestrator.py — Central routing and coordination agent.

Responsibilities:
  1. Detect whether the project has a frontend (to decide if design/appflow run).
  2. Determine the next agent in the fixed execution sequence.
  3. Update Tracker.md after each agent completes.
  4. Route to END when all required files are populated.

Execution sequence:
  structuring → prd → trd → schema → [design → appflow] → rules → implementation → tracker → modules → END
"""
from pathlib import Path
from planner.state import PlannerState
from planner.agents.tracker_agent import tracker_agent

# Keyword signals that the project includes a frontend
_FRONTEND_KEYWORDS = {
    "frontend", "front-end", "ui", "ux", "web app", "webapp",
    "mobile", "react", "vue", "angular", "next.js", "nuxt",
    "flutter", "swift", "android", "ios", "html", "css",
    "dashboard", "interface", "screen", "page", "component",
}

# Fixed sequence: (agent_name, target_file)
_SEQUENCE = [
    ("structuring",     "StructuredIdea.md"),
    ("prd",             "PRD.md"),
    ("trd",             "TRD.md"),
    ("schema",          "Schema.md"),
    ("design",          "DesignDecisions.md"),   # conditional on has_frontend
    ("appflow",         "AppFlow.md"),            # conditional on has_frontend
    ("rules",           "Rules.md"),
    ("implementation",  "ImplementationPlan.md"),
    ("tracker",         "Tracker.md"),
    ("modules",         "MODULES/"),             # only if modules requested
]

_FRONTEND_AGENTS = {"design", "appflow"}


def _detect_frontend(state: PlannerState) -> bool:
    """
    Return True if the project idea mentions a frontend.
    Uses word-boundary regex to avoid false positives like 'no frontend'.
    """
    import re
    planner_dir = Path(state.project_path)

    # Patterns that indicate a deliberate negation of frontend
    _NEGATION_PHRASES = re.compile(
        r"\b(no|without|purely?|headless|backend.?only|cli.?only)\b.{0,20}"
        r"\b(frontend|ui|web|mobile|interface)\b",
        re.IGNORECASE,
    )
    # Affirmative frontend signal: keyword as a standalone word (not negated)
    _AFFIRMATIVE = re.compile(
        r"\b(react|vue|angular|next\.js|nuxt|flutter|swift|android|ios|html|css|"
        r"web app|webapp|dashboard|web interface|mobile app|frontend|front.end|"
        r"user interface)\b",
        re.IGNORECASE,
    )

    for fname in ("StructuredIdea.md", "TRD.md"):
        fpath = planner_dir / fname
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")
        # Remove negation sentences before checking affirmatives
        text_without_negations = _NEGATION_PHRASES.sub("", text)
        if _AFFIRMATIVE.search(text_without_negations):
            return True
    return False



def _file_is_populated(planner_dir: Path, filename: str) -> bool:
    """Return True if the target file exists and is non-empty."""
    if filename.endswith("/"):  # directory (e.g. MODULES/)
        return True  # modules are optional — don't block
    path = planner_dir / filename
    return path.exists() and path.stat().st_size > 0


def orchestrator(state: PlannerState) -> PlannerState:
    """
    Determine which agent should run next based on what files are already populated.
    Update has_frontend, write Tracker.md status, and set next_agent.
    """
    planner_dir = Path(state.project_path)

    # Detect frontend once per run (re-detect on each orchestrator pass in case TRD was just written)
    state.has_frontend = _detect_frontend(state)

    # Walk the sequence and find the first unpopulated required file
    for agent_name, target_file in _SEQUENCE:
        # Skip frontend-only agents if no frontend
        if agent_name in _FRONTEND_AGENTS and not state.has_frontend:
            continue
        # Skip modules in the main run sequence (they're triggered explicitly)
        if agent_name == "modules":
            continue

        if not _file_is_populated(planner_dir, target_file):
            state.next_agent = agent_name
            state.current_file = target_file
            # Update Tracker.md on each routing decision
            _update_tracker(state, agent_name)
            return state

    # All required files are populated — we're done
    state.status = "done"
    state.next_agent = ""
    print("\n✅  All planning files are complete! Run `planner status` to review.\n")
    return state


def _update_tracker(state: PlannerState, next_agent: str) -> None:
    """Write a minimal status line to Tracker.md indicating what's running next."""
    planner_dir = Path(state.project_path)
    tracker_path = planner_dir / "Tracker.md"
    # Only update if Tracker.md already exists (avoid creating it prematurely)
    if tracker_path.exists() and tracker_path.stat().st_size > 0:
        # The tracker_agent handles full rewrites; here we just print progress
        pass
    print(f"  ▶  Running: {next_agent} → {state.current_file}")


def run_consistency_check(state: PlannerState) -> str:
    """
    Read-only pass across all PLANNER/ files checking for contradictions.
    Returns a Markdown report string. Does NOT modify any files.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from planner.agents._base import invoke_llm_safe, load_context

    planner_dir = Path(state.project_path)
    files_to_check = [
        "StructuredIdea.md", "PRD.md", "TRD.md", "Schema.md",
        "DesignDecisions.md", "AppFlow.md", "Rules.md", "ImplementationPlan.md",
    ]
    ctx = load_context(state, *files_to_check)
    combined = ""
    for fname in files_to_check:
        content = ctx.get(fname, "").strip()
        if content:
            combined += f"\n\n## {fname}\n{content}"

    if not combined.strip():
        return "No planning files found to check."

    system = """You are a technical documentation auditor. 
Your job is to check a set of planning documents for contradictions, mismatches, and inconsistencies.

Look for:
- Schema tables mentioned in TRD/AppFlow but not defined in Schema.md.
- Features in PRD that are missing from ImplementationPlan.md.
- Tech stack choices in TRD that conflict with Constraints.md.
- Screens in AppFlow.md not covered by PRD features.
- Rules that contradict the chosen tech stack.

Output: A Markdown report. For each issue found:
  - **Issue**: What the contradiction is.
  - **Files involved**: Which files conflict.
  - **Suggestion**: Which file should be corrected.

If no issues found, write: ✅ No contradictions detected.
"""
    messages = [SystemMessage(content=system), HumanMessage(content=combined)]
    return invoke_llm_safe(messages)
