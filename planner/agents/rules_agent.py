"""
rules_agent.py — Coding conventions and AI behavior rules agent.
Reads: StructuredIdea.md, TRD.md, Constraints.md
Writes: Rules.md
"""
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file, get_update_instructions

SYSTEM_PROMPT = """You are a senior engineering lead who writes engineering playbooks.
Your job is to write Rules.md — the coding standards and AI agent behaviour rules for this project.

Rules.md MUST cover:
1. **Coding Conventions**:
   - Naming conventions (variables, files, functions, classes).
   - Code style and formatting (linter, formatter, style guide).
   - Folder/module structure rules.
2. **Patterns to Follow**:
   - Error handling approach (exceptions vs result types, logging).
   - Validation strategy (where and how to validate inputs).
   - Testing requirements (unit vs integration, coverage targets, mocking rules).
3. **AI Agent Behaviour Rules** (what the AI is allowed / not allowed to do):
   - What files the AI can modify vs must not touch.
   - When the AI must ask before changing something (scope creep guard).
   - Banned operations (e.g. no destructive database migrations without user confirmation).
4. **Security Rules**: Auth, secrets management, input sanitisation.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- Be specific to the chosen tech stack from TRD.md.
- Rules must be enforceable — avoid vague guidance like \"write clean code\".
"""


def _gather(state: PlannerState) -> PlannerState:
    ctx = load_context(state, "StructuredIdea.md", "TRD.md", "Constraints.md")
    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    trd_content = ctx.get("TRD.md", "").strip()
    constraints = ctx.get("Constraints.md", "").strip()

    questions = []
    if not structured_idea:
        questions.append("StructuredIdea.md is empty. Cannot generate rules.")
    if not trd_content:
        questions.append("TRD.md is missing — cannot write Rules without it")
    if not constraints:
        questions.append("Constraints.md is missing — cannot write Rules without it")

    state.pending_questions = questions
    if questions:
        state.status = "needs_input"
        state.calling_agent = "rules"
    else:
        state.status = "drafting"
    return state


def _write(state: PlannerState) -> PlannerState:
    ctx = load_context(state, "StructuredIdea.md", "TRD.md", "Constraints.md")

    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    trd_content = ctx.get("TRD.md", "").strip()
    constraints = ctx.get("Constraints.md", "").strip()

    user_content = f"Structured Idea:\n{structured_idea}\n"
    if trd_content:
        user_content += f"\nTRD:\n{trd_content}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"
    if state.grill_answers:
        user_content += "\nAdditional context from user:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "Rules.md")
    if update_inst:
        user_content += update_inst

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "Rules.md", content)

    state.current_file = "Rules.md"
    state.status = "drafting"
    state.next_agent = "implementation"
    state.phase = "done"
    return state


def rules_agent(state: PlannerState) -> PlannerState:
    """Generate Rules.md from StructuredIdea + TRD + Constraints, using gather/write phases."""
    if state.phase == "gather":
        return _gather(state)
    elif state.phase == "write":
        return _write(state)
    return state
