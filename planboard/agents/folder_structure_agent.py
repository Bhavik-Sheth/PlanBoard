from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.state import PlannerState
from planboard.tools import read_file, write_file
from planboard.agents._base import invoke_llm_safe, strip_markdown_fence, get_update_instructions

FOLDER_STRUCTURE_SYSTEM_PROMPT = """You are an expert Software Architect AI.
Your only goal is to generate a comprehensive, clear, and professional `FolderStructure.md` file (which shows the proposed/actual project folder structure with clear descriptions for each directory/file) based on Structured Idea, Constraints, PRD, TRD, Schema, DesignDecisions, AppFlow.

Specifications:
- The output must show the proposed project folder structure using standard visual directory trees.
- Provide clear descriptions for each directory/file below or alongside the structure.
- Do NOT wrap the entire output in markdown code fences.
- Do NOT output any conversational text.
"""


def _gather(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    structured_idea_path = planboard_dir / "StructuredIdea.md"

    if not structured_idea_path.exists():
        state.pending_questions = ["StructuredIdea.md is missing. Please structure your idea first."]
        state.status = "needs_input"
        state.current_file = "ARCHITECTURE_DIAGRAMS/FolderStructure.md"
        state.calling_agent = "folder_structure"
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

    update_inst = get_update_instructions(state, "ARCHITECTURE_DIAGRAMS/FolderStructure.md")
    if update_inst:
        user_content += update_inst

    messages = [
        SystemMessage(content=FOLDER_STRUCTURE_SYSTEM_PROMPT),
        HumanMessage(content=user_content)
    ]

    content = strip_markdown_fence(invoke_llm_safe(messages))

    # Write file to disk
    diagrams_dir = planboard_dir / "ARCHITECTURE_DIAGRAMS"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    filepath = diagrams_dir / "FolderStructure.md"
    write_file(str(filepath), content, overwrite=True)

    state.current_file = "ARCHITECTURE_DIAGRAMS/FolderStructure.md"
    state.status = "drafting"
    state.phase = "done"

    return state


def folder_structure_agent(state: PlannerState) -> PlannerState:
    """
    Folder Structure Agent node: reads StructuredIdea.md, PRD, TRD, Schema, etc.,
    generates FolderStructure.md and updates state.
    """
    if state.phase == "gather":
        return _gather(state)
    elif state.phase == "write":
        return _write(state)
    return state
