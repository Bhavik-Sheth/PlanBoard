"""
structuring_agent.py — Converts RawIdea.md into a clean StructuredIdea.md.
Reads: RawIdea.md
Writes: StructuredIdea.md
"""
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file

SYSTEM_PROMPT = """You are an expert product strategist. Your job is to take a raw, unstructured idea 
description and produce a clean, well-structured problem statement in Markdown.

The output MUST include:
1. **App Name / Working Title** (infer from context if not stated)
2. **Core Problem**: The specific pain point this app solves.
3. **Proposed Solution**: What the app does at a high level.
4. **Key Capabilities**: Bullet list of 5-10 concrete capabilities.
5. **Platform & Audience**: Who will use it and on what platform (web, mobile, CLI, desktop, API, etc.).
6. **Technology Preferences** (if mentioned by the user, otherwise note "Not specified").
7. **Constraints** (budget, timeline, team size — anything mentioned by user).

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- Be faithful to the user's words — do not invent features they didn't describe.
- If something is ambiguous, represent it as-is rather than guessing.
"""


def structuring_agent(state: PlannerState) -> PlannerState:
    """Convert RawIdea.md → StructuredIdea.md."""
    ctx = load_context(state, "RawIdea.md")
    raw_idea = ctx.get("RawIdea.md", "").strip()

    if not raw_idea:
        state.pending_questions = [
            "RawIdea.md is empty. Please describe your project idea first using `planner describe <text>`."
        ]
        state.status = "needs_input"
        state.calling_agent = "structuring"
        return state

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Raw Idea:\n{raw_idea}"),
    ]

    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "StructuredIdea.md", content)

    state.structured_idea = content
    state.current_file = "StructuredIdea.md"
    state.status = "drafting"
    # Route to orchestrator so it evaluates the sequence naturally.
    # Do NOT hardcode "prd" here — the orchestrator will detect StructuredIdea.md
    # is populated and advance to the next unpopulated file in its sequence.
    state.next_agent = "orchestrator"
    return state
