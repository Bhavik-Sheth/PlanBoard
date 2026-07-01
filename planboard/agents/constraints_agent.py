"""
constraints_agent.py — Constraints agent.
Reads: StructuredIdea.md
Writes: Constraints.md
"""
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.state import PlannerState
from planboard.tools import read_file
from planboard.agents._base import invoke_llm_safe, strip_markdown_fence, write_agent_file, get_update_instructions

CONSTRAINTS_SYSTEM_PROMPT = """You are a software architect specializing in defining project constraints and guardrails.
Your goal is to generate a strict, clear, and professional `Constraints.md` file based on a Structured Idea.

The Constraints file MUST contain the following sections:
1. **Technical Constraints**: Platform (OS, runtime, language version), library restrictions, no-go dependencies.
2. **Budget & Resource Constraints**: Maximum monthly cost, restrictions on paid APIs, infrastructure budget. If not mentioned, assume $0/month (Free tier only).
3. **Legal & Compliance**: Data privacy rules, licensing restrictions, what data cannot be stored.
4. **Performance Floor**: Minimum acceptable latency/throughput the system must meet (e.g. page loads < 2s).
5. **Things AI Must Never Do**: Strict list of no-go actions for subsequent coding agents (e.g. destructive database operations without confirmation, pushing to production, deleting files).
6. **Hard Assumptions**: Facts assumed true that must not be violated.

Rules:
- Write the output in clean, production-ready Markdown.
- Do NOT wrap your entire output in markdown code block backticks (i.e. do not output ```markdown ... ``` surrounding the whole document). Start writing the markdown content directly.
- Be specific, detailed, and realistic based on the provided Structured Idea.
- Distinguish hard constraints (immovable) from soft preferences. Write in absolute terms: "must not", "never", "always".
"""


def _gather(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    structured_idea_path = planboard_dir / "StructuredIdea.md"

    if not structured_idea_path.exists():
        state.pending_questions = ["StructuredIdea.md is missing. Please structure your idea first."]
        state.status = "needs_input"
        state.current_file = "Constraints.md"
        state.calling_agent = "constraints"
        return state

    structured_idea = read_file(str(structured_idea_path)).strip()
    if not structured_idea:
        state.pending_questions = ["The StructuredIdea.md file is empty. Please describe and structure your idea first."]
        state.status = "needs_input"
        state.current_file = "Constraints.md"
        state.calling_agent = "constraints"
        return state

    state.pending_questions = []
    state.status = "drafting"
    return state


def _write(state: PlannerState) -> PlannerState:
    planboard_dir = Path(state.project_path)
    structured_idea_path = planboard_dir / "StructuredIdea.md"
    structured_idea = read_file(str(structured_idea_path)).strip()

    user_content = f"Structured Idea:\n{structured_idea}\n"
    if state.grill_answers:
        user_content += f"\nAdditional Details (from user feedback):\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "Constraints.md")
    if update_inst:
        user_content += update_inst

    messages = [
        SystemMessage(content=CONSTRAINTS_SYSTEM_PROMPT),
        HumanMessage(content=user_content)
    ]

    constraints_content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "Constraints.md", constraints_content)

    state.current_file = "Constraints.md"
    state.status = "drafting"
    state.phase = "done"

    return state


def constraints_agent(state: PlannerState) -> PlannerState:
    """
    Constraints Agent node: reads StructuredIdea.md,
    invokes LLM to generate Constraints.md, writes it to disk, and updates state.
    Handles gather/write two-phase lifecycle.
    """
    if state.phase == "gather":
        return _gather(state)
    elif state.phase == "write":
        return _write(state)
    return state
