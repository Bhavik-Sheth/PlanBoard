"""
orchestrator.py — Central routing and coordination agent.
"""
import sys
from pathlib import Path
import re
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState, save_state
from planner.agents.tracker_agent import tracker_agent
from planner.agents._base import invoke_llm_safe, strip_markdown_fence

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
    ("constraints",     "Constraints.md"),
    ("prd",             "PRD.md"),
    ("trd",             "TRD.md"),
    ("schema",          "Schema.md"),
    ("design",          "DesignDecisions.md"),   # conditional on has_frontend
    ("appflow",         "AppFlow.md"),            # conditional on has_frontend
    ("rules",           "Rules.md"),
    ("implementation",  "ImplementationPlan.md"),
    ("tracker",         "Tracker.md"),
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
    path = planner_dir / filename
    return path.exists() and path.stat().st_size > 0


# Prompts for Structuring and Hybrid Structuring

FROM_SCRATCH_STRUCTURING_PROMPT = """You are an expert product strategist.
Read the raw idea below and produce a clean, detailed, well-structured problem statement in Markdown.

The output MUST contain:
1. **Product Name / Working Title**
2. **Problem Statement**:
   - What problem exists
   - Who has it (target audience/personas)
   - Why current solutions fail
3. **Solution Overview**: What the proposed solution does at a high level.
4. **Key Goals & Non-Goals**: Clear list of what this project aims to achieve and what is explicitly out of scope.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences (e.g. do not output ```markdown ... ```).
- Be faithful to the raw idea — do not invent features they didn't describe.
"""

HYBRID_STRUCTURING_PROMPT = """You are an expert product strategist and systems architect.
Read the problem statement and the proposed solution from the raw idea below.
Produce a structured planning document in Markdown with the following exact headings:

## Problem Statement (Structured)
[Cleaned, specific version of the PS. Who is affected, what is the pain, why it matters, scope of the problem.]

## Solution Overview
[Cleaned, specific version of the proposed solution. What it builds, how it solves the PS, what it explicitly does not do.]

## Fit Analysis
[Analyze if the proposed solution actually solves the stated PS. Identify:
- Gaps: aspects of the PS the solution doesn't address
- Assumptions: things the solution assumes that the PS doesn't guarantee
- Risks: where the solution may fail to solve the problem in edge cases]

## Validated Scope
[Synthesized final scope: the intersection of what the PS requires and what the solution proposes. This is what the PRD agent will build against.]

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- Be honest and detailed in the Fit Analysis.
"""


def run_startup_flow(state: PlannerState) -> PlannerState:
    planner_dir = Path(state.project_path)
    si_path = planner_dir / "StructuredIdea.md"
    tracker_path = planner_dir / "Tracker.md"
    
    if si_path.exists() and si_path.stat().st_size > 0:
        print("\nWelcome back to PlannerX.\n")
        print("Resuming session. Last status:")
        if tracker_path.exists():
            print(tracker_path.read_text(encoding="utf-8"))
        else:
            print("[Tracker.md not found]")
            
        try:
            choice = input("\nContinue from where we left off? [yes/no]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "yes"
            
        if choice in ("n", "no"):
            state = run_mode_selection(state)
        else:
            print("\nResuming main sequence...")
    else:
        state = run_mode_selection(state)
        
    return state


def run_mode_selection(state: PlannerState) -> PlannerState:
    planner_dir = Path(state.project_path)
    
    from planner.tools import scaffold_planner
    scaffold_planner(str(planner_dir.parent))
    
    print("\nWelcome to PlannerX.\n")
    print("How would you like to start?\n")
    print("  [1] From scratch — I have a raw idea, help me plan it fully")
    print("  [2] PS + Idea — I have a problem statement and a proposed solution\n")
    
    while True:
        try:
            choice = input("Type 1 or 2 to begin: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "1"
        if choice in ("1", "2"):
            break
        print("Invalid choice. Please enter 1 or 2.")
        
    if choice == "1":
        state.mode = "from_scratch"
        print("\n--- Mode A: From Scratch ---")
        print("Please describe your project idea in plain text. You can type multiple lines.")
        print("When you are finished, type /done on a new line or press Enter on an empty line.")
        
        lines = []
        while True:
            try:
                line = input().strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line == "/done" or (not line and lines):
                break
            lines.append(line)
            
        raw_idea = "\n".join(lines).strip()
        raw_idea_path = planner_dir / "RawIdea.md"
        raw_idea_path.write_text(raw_idea, encoding="utf-8")
        print(f"\n✅ RawIdea.md written.")
        
        print("⏳ Structuring idea via LLM...")
        state = run_structuring_subroutine(state, raw_idea)
        print("✅ StructuredIdea.md generated.")
        
    else:
        state.mode = "ps_idea_hybrid"
        print("\n--- Mode B: PS + Idea (Hybrid) ---")
        
        print("Paste or describe the Problem Statement (PS).")
        print("This is the problem you are solving — not your solution.")
        print("Type /done when finished or press Enter on an empty line.")
        
        ps_lines = []
        while True:
            try:
                line = input().strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line == "/done" or (not line and ps_lines):
                break
            ps_lines.append(line)
            
        ps_content = "\n".join(ps_lines).strip()
        
        print("\nNow describe your proposed solution to this PS.")
        print("What will you build? How does it address the problem?")
        print("Type /done when finished or press Enter on an empty line.")
        
        sol_lines = []
        while True:
            try:
                line = input().strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line == "/done" or (not line and sol_lines):
                break
            sol_lines.append(line)
            
        sol_content = "\n".join(sol_lines).strip()
        
        raw_idea_path = planner_dir / "RawIdea.md"
        raw_idea_content = f"## Problem Statement\n{ps_content}\n\n## Proposed Solution\n{sol_content}\n"
        raw_idea_path.write_text(raw_idea_content, encoding="utf-8")
        print(f"\n✅ RawIdea.md written.")
        
        revision_count = 0
        while True:
            print("⏳ Running Hybrid Structuring via LLM...")
            state = run_hybrid_structuring_subroutine(state, ps_content, sol_content)
            
            fit_analysis = state.fit_analysis
            print("\n" + "="*60)
            print("FIT ANALYSIS")
            print("="*60)
            print(fit_analysis)
            print("="*60 + "\n")
            
            revision_count += 1
            if revision_count >= 5:
                print("Max revisions reached. Proceeding with current scope.")
                break
                
            try:
                action = input("Proceed with current scope? Or would you like to revise your solution first? [proceed/revise]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                action = "proceed"
                
            if action in ("p", "proceed", "yes", "y"):
                break
                
            print("\nDescribe your revised solution:")
            print("Type /done when finished or press Enter on an empty line.")
            rev_lines = []
            while True:
                try:
                    line = input().strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if line == "/done" or (not line and rev_lines):
                    break
                rev_lines.append(line)
            sol_content = "\n".join(rev_lines).strip()
            
            raw_idea_content = f"## Problem Statement\n{ps_content}\n\n## Proposed Solution\n{sol_content}\n"
            raw_idea_path.write_text(raw_idea_content, encoding="utf-8")
            
    if "StructuredIdea.md" not in state.approved_files:
        state.approved_files.append("StructuredIdea.md")
        
    save_state(state)
    return state


def run_structuring_subroutine(state: PlannerState, raw_idea: str) -> PlannerState:
    messages = [
        SystemMessage(content=FROM_SCRATCH_STRUCTURING_PROMPT),
        HumanMessage(content=f"Raw Idea:\n{raw_idea}"),
    ]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    
    si_path = Path(state.project_path) / "StructuredIdea.md"
    si_path.write_text(content, encoding="utf-8")
    state.structured_idea = content
    return state


def run_hybrid_structuring_subroutine(state: PlannerState, ps: str, sol: str) -> PlannerState:
    raw_idea_text = f"## Problem Statement\n{ps}\n\n## Proposed Solution\n{sol}\n"
    messages = [
        SystemMessage(content=HYBRID_STRUCTURING_PROMPT),
        HumanMessage(content=raw_idea_text),
    ]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    
    si_path = Path(state.project_path) / "StructuredIdea.md"
    si_path.write_text(content, encoding="utf-8")
    state.structured_idea = content
    
    fit_match = re.search(r"## Fit Analysis\s*(.*?)(?=\n##|$)", content, re.DOTALL | re.IGNORECASE)
    if fit_match:
        state.fit_analysis = fit_match.group(1).strip()
    else:
        state.fit_analysis = "No fit analysis section generated by LLM."
        
    return state


def generate_bullet_summary(content: str) -> str:
    messages = [
        SystemMessage(content="You are a technical editor. Summarize the following document into exactly 2-3 bullet points highlighting the most important decisions, requirements, or features specified in it. Be extremely concise. Start directly with the bullet points, using '-' as bullet character."),
        HumanMessage(content=content)
    ]
    try:
        return invoke_llm_safe(messages).strip()
    except Exception:
        return "- Draft updated successfully.\n- Details captured in file."


def _update_tracker_disk(state: PlannerState, current_file: str, next_agent: str, status: str) -> None:
    orig_curr = state.current_file
    orig_next = state.next_agent
    orig_status = state.status

    # Temporarily set state fields for tracker_agent to write correctly
    state.current_file = current_file
    state.next_agent = next_agent
    state.status = status

    tracker_agent(state)

    # Restore original state fields
    state.current_file = orig_curr
    state.next_agent = orig_next
    state.status = orig_status


def orchestrator(state: PlannerState) -> PlannerState:
    """
    Orchestrate the flow of planning files.
    - If the last agent's file was just written, display summary, mark Needs Review, and pause.
    - Otherwise, find the next unpopulated / unapproved file and run its agent.
    """
    planner_dir = Path(state.project_path)

    # Detect if we have a frontend project
    state.has_frontend = _detect_frontend(state)

    # 1. Check if the active file was just written and needs user review
    if state.current_file and state.current_file not in state.approved_files:
        path = planner_dir / state.current_file
        if path.exists() and path.stat().st_size > 0:
            # File was just written! Show review prompt
            content = path.read_text(encoding="utf-8")
            summary = generate_bullet_summary(content)
            
            print(f"\n✅ {state.current_file} written.")
            print("Key decisions:")
            print(summary)
            print(f"\nType /approve {state.current_file} to accept, or describe changes to revise it.\n")
            
            state.active_revision_target = state.current_file
            state.status = "needs_review"
            state.next_agent = ""
            
            # Update Tracker.md to show Needs Review
            _update_tracker_disk(state, current_file=state.current_file, next_agent="", status="needs_review")
            save_state(state)
            return state

    # 2. Find the first file in sequence that is not approved
    for agent_name, target_file in _SEQUENCE:
        # Skip frontend-only agents if no frontend
        if agent_name in _FRONTEND_AGENTS and not state.has_frontend:
            continue

        if target_file not in state.approved_files:
            state.next_agent = agent_name
            state.current_file = target_file
            state.status = "drafting"
            
            # Prepare context for the next agent
            upstream_map = {
                "Constraints.md": ["StructuredIdea.md"],
                "PRD.md": ["StructuredIdea.md", "Constraints.md"],
                "TRD.md": ["StructuredIdea.md", "Constraints.md", "PRD.md"],
                "Schema.md": ["StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md"],
                "DesignDecisions.md": ["StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md"],
                "AppFlow.md": ["StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md"],
                "Rules.md": ["StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md", "Schema.md"],
                "ImplementationPlan.md": ["StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md", "Schema.md", "Rules.md"],
            }
            
            if target_file in upstream_map:
                from planner.agents._base import load_context
                load_context(state, *upstream_map[target_file])
                
            # Update Tracker.md to show In Progress
            _update_tracker_disk(state, current_file=target_file, next_agent=agent_name, status="drafting")
            save_state(state)
            return state

    # All required files are approved!
    state.status = "done"
    state.next_agent = ""
    print("\n✅  All planning files are complete! Run `planner finalize` to generate CLAUDE.md.\n")
    _update_tracker_disk(state, current_file="Tracker.md", next_agent="", status="done")
    save_state(state)
    return state


def run_consistency_check(state: PlannerState) -> str:
    """
    Read-only pass across all PLANNER/ files checking for contradictions.
    Returns a Markdown report string. Does NOT modify any files.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from planner.agents._base import invoke_llm_safe, load_context

    planner_dir = Path(state.project_path)
    files_to_check = [
        "StructuredIdea.md", "Constraints.md", "PRD.md", "TRD.md", "Schema.md",
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
