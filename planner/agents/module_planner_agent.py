"""
module_planner_agent.py — Module spec planner agent.
Reads: all PLANNER/*.md files (StructuredIdea, TRD, Schema, Rules, Constraints)
Writes: MODULES/<name>.md  (one file per module, minimal and specific)

The module name to plan is taken from state.context_files["__module_name__"] if set,
or from the first unfilled module file found in MODULES/.
"""
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence
from planner.files.writer import write_planner_file

SYSTEM_PROMPT = """You are a backend module designer. Your job is to write a minimal, focused module spec.

The module spec MUST cover (keep it SHORT — this is a working file for execution, not planning):
1. **Purpose**: One paragraph on what this module does and why it exists.
2. **Role in System**: How it fits into the overall architecture (what calls it, what it calls).
3. **Tech Stack for This Module**: Specific imports, packages, APIs, services this module uses.
   Include exact package names and versions if relevant.
4. **Key Functions / Classes**: A brief list of the main public interfaces this module exposes.
5. **Constraints & Rules** (module-specific): Inherited from project-level Constraints.md/Rules.md,
   narrowed to only what applies to this module. Plus any module-specific gotchas.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- Keep it short: aim for 200-400 words. This is a working note, not a design document.
- Be specific to the named module — do not describe the whole system.
"""


def module_planner_agent(state: PlannerState) -> PlannerState:
    """Generate MODULES/<name>.md for the requested module."""
    module_name = state.context_files.get("__module_name__", "").strip()

    if not module_name:
        # No module name set — end the run
        state.status = "done"
        state.next_agent = ""
        return state

    # Load context
    ctx = load_context(state, "StructuredIdea.md", "TRD.md", "Schema.md", "Rules.md", "Constraints.md")
    structured_idea = ctx.get("StructuredIdea.md", "")
    trd_content = ctx.get("TRD.md", "")
    schema_content = ctx.get("Schema.md", "")
    rules_content = ctx.get("Rules.md", "")
    constraints = ctx.get("Constraints.md", "")

    user_content = f"Module Name: {module_name}\n"
    if structured_idea:
        user_content += f"\nProject Overview:\n{structured_idea}\n"
    if trd_content:
        user_content += f"\nTRD (Tech Stack & Architecture):\n{trd_content[:2000]}\n"  # truncate if huge
    if schema_content:
        user_content += f"\nSchema:\n{schema_content[:1500]}\n"
    if rules_content:
        user_content += f"\nRules:\n{rules_content[:1000]}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"
    if state.grill_answers:
        user_content += "\nAdditional context:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))

    modules_dir = Path(state.project_path) / "MODULES"
    modules_dir.mkdir(exist_ok=True)
    module_path = modules_dir / f"{module_name}.md"
    write_planner_file(module_path, content, force=True)

    state.current_file = f"MODULES/{module_name}.md"
    state.status = "done"
    state.next_agent = ""
    # Clear the module name so repeated calls don't re-plan the same module
    state.context_files.pop("__module_name__", None)
    return state
