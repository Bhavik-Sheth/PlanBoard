from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.state import PlannerState
from planboard.tools import read_file, write_file
from planboard.agents._base import invoke_llm_safe, strip_markdown_fence, get_update_instructions

SYSTEM_ARCHITECTURE_SYSTEM_PROMPT = """You are an expert Software Architect AI.
Your only goal is to generate a comprehensive, clear, and professional `SystemArchitecture.md` file (which shows the high-level system architecture, components, and their connections using a HORIZONTAL ASCII diagram inside a markdown code block, and a brief explanation below) based on Structured Idea, Constraints, PRD, TRD, Schema, DesignDecisions, AppFlow.

Specifications:
- The output must contain a HORIZONTAL ASCII diagram inside a markdown code block showing the high-level system architecture, components, and their connections.
- Include a brief explanation below the diagram.
- Do NOT wrap the entire output in markdown code fences, only the ASCII diagram itself.
- All ASCII diagrams must be horizontal, using arrows (e.g., `-->` or `==>`) and text boxes (e.g., `[Component]`) to represent structures and flows.
- Make sure all ASCII diagrams are clean and fit within a standard terminal width (80-100 characters).
- Do NOT output any conversational text.
"""


def _gather(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    structured_idea_path = planboard_dir / "StructuredIdea.md"

    if not structured_idea_path.exists():
        state.pending_questions = ["StructuredIdea.md is missing. Please structure your idea first."]
        state.status = "needs_input"
        state.current_file = "ARCHITECTURE_DIAGRAMS/SystemArchitecture.md"
        state.calling_agent = "system_architecture"
        return state

    state.pending_questions = []
    state.status = "drafting"
    return state


def _write(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    
    # Read upstream files loaded by load_context
    structured_idea = state.context_files.get("StructuredIdea.md", "").strip()
    constraints = state.context_files.get("Constraints.md", "").strip()
    prd = state.context_files.get("PRD.md", "").strip()
    trd = state.context_files.get("TRD.md", "").strip()
    schema = state.context_files.get("Schema.md", "").strip()
    design = state.context_files.get("DesignDecisions.md", "").strip()
    appflow = state.context_files.get("AppFlow.md", "").strip()

    # Build prompt messages
    user_content = f"Structured Idea:\n{structured_idea}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"
    if prd:
        user_content += f"\nPRD:\n{prd}\n"
    if trd:
        user_content += f"\nTRD:\n{trd}\n"
    if schema:
        user_content += f"\nSchema:\n{schema}\n"
    if design:
        user_content += f"\nDesign Decisions:\n{design}\n"
    if appflow:
        user_content += f"\nApp Flow:\n{appflow}\n"

    if state.grill_answers:
        user_content += f"\nAdditional Details (from user feedback):\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "ARCHITECTURE_DIAGRAMS/SystemArchitecture.md")
    if update_inst:
        user_content += update_inst

    messages = [
        SystemMessage(content=SYSTEM_ARCHITECTURE_SYSTEM_PROMPT),
        HumanMessage(content=user_content)
    ]

    content = strip_markdown_fence(invoke_llm_safe(messages))

    # Write file to disk
    diagrams_dir = planboard_dir / "ARCHITECTURE_DIAGRAMS"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    filepath = diagrams_dir / "SystemArchitecture.md"
    write_file(str(filepath), content, overwrite=True)

    state.current_file = "ARCHITECTURE_DIAGRAMS/SystemArchitecture.md"
    state.status = "drafting"
    state.phase = "done"

    return state


def system_architecture_agent(state: PlannerState) -> PlannerState:
    """
    System Architecture Agent node: reads StructuredIdea.md, PRD, TRD, Schema, etc.,
    generates SystemArchitecture.md and updates state.
    """
    if state.phase == "gather":
        return _gather(state)
    elif state.phase == "write":
        return _write(state)
    return state
