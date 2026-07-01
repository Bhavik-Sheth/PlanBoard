from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.state import PlannerState
from planboard.tools import read_file, write_file
from planboard.agents._base import invoke_llm_safe, strip_markdown_fence, get_update_instructions

PRD_SYSTEM_PROMPT = """You are a Principal Product Manager expert at writing Product Requirements Documents (PRD).
Your only goal is to generate a comprehensive, clear, and professional `PRD.md` file based on a Structured Idea and any optional Constraints.

The PRD MUST contain the following sections:
1. **Problem Statement**: Why this app exists and what problem it solves.
2. **Target Users**: Personas and demographics of who will use the app.
3. **Core Features**: List of must-have features vs. nice-to-have features.
4. **Out of Scope**: Explicitly define what the app will NOT do in this phase/version.
5. **User Stories & Acceptance Criteria**: Clear user scenarios and how to verify they work.
6. **Success Metrics**: How we measure if the product is successful.
7. **Edge Cases**: Design consideration for offline behavior, invalid input, concurrent actions, rate limits, etc.

Rules:
- Write the output in clean, production-ready Markdown.
- Do NOT wrap your entire output in markdown code block backticks (i.e. do not output ```markdown ... ``` surrounding the whole document). Start writing the markdown content directly.
- Be specific, detailed, and realistic based on the provided Structured Idea.
- If any Constraints are provided, ensure the features and scope strictly adhere to them.
"""


def _gather(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    structured_idea_path = planboard_dir / "StructuredIdea.md"

    if not structured_idea_path.exists():
        state.pending_questions = ["StructuredIdea.md is missing. Please structure your idea first."]
        state.status = "needs_input"
        state.current_file = "PRD.md"
        state.calling_agent = "prd"
        return state

    structured_idea = read_file(str(structured_idea_path)).strip()
    if not structured_idea:
        state.pending_questions = ["The StructuredIdea.md file is empty. Please describe and structure your idea first."]
        state.status = "needs_input"
        state.current_file = "PRD.md"
        state.calling_agent = "prd"
        return state

    state.pending_questions = []
    state.status = "drafting"
    return state


def _write(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    structured_idea_path = planboard_dir / "StructuredIdea.md"
    constraints_path = planboard_dir / "Constraints.md"

    structured_idea = read_file(str(structured_idea_path)).strip()
    constraints = ""
    if constraints_path.exists():
        constraints = read_file(str(constraints_path)).strip()

    # Build prompt messages
    user_content = f"Structured Idea:\n{structured_idea}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"

    if state.grill_answers:
        user_content += f"\nAdditional Details (from user feedback):\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "PRD.md")
    if update_inst:
        user_content += update_inst

    messages = [
        SystemMessage(content=PRD_SYSTEM_PROMPT),
        HumanMessage(content=user_content)
    ]

    prd_content = strip_markdown_fence(invoke_llm_safe(messages))

    # Write PRD.md to disk
    prd_path = planboard_dir / "PRD.md"
    write_file(str(prd_path), prd_content, overwrite=True)

    state.current_file = "PRD.md"
    state.structured_idea = structured_idea
    state.status = "drafting"
    state.phase = "done"

    return state


def prd_agent(state: PlannerState) -> PlannerState:
    """
    PRD Agent node: reads StructuredIdea.md and Constraints.md from disk,
    invokes the configured LLM to generate the PRD content, writes it to PRD.md,
    and updates the state. Handles gather/write two-phase lifecycle.
    """
    if state.phase == "gather":
        return _gather(state)
    elif state.phase == "write":
        return _write(state)
    return state
