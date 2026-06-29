"""
implementation_agent.py — Implementation phases planner agent.
Reads: PRD.md, TRD.md, Schema.md
Writes: ImplementationPlan.md
"""
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file, get_update_instructions

SYSTEM_PROMPT = """You are a principal engineer who breaks large projects into phased implementation plans.
Your job is to write ImplementationPlan.md.

ImplementationPlan.md MUST cover:
1. **Phases** (build in vertical slices — each phase delivers working, testable functionality):
   For each phase:
   - **Goal**: The single sentence outcome of this phase.
   - **Scope**: What gets built (DB layer first → backend → frontend per feature).
   - **Deliverable**: Concrete output (e.g. \"users can log in via email/password\").
   - **Estimated Time**: Rough dev time (hours or days).
   - **Dependencies**: Which prior phases must be complete.
   - **Checklist**: Sub-tasks as a markdown checklist [ ].
2. **MVP Cut-Line**: Clearly mark which phase is the minimum viable product.
3. **Post-MVP Phases**: Label remaining phases as \"V2\" or \"nice-to-have\".

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- Vertical slices — never build an entire layer (all DB tables) before touching backend.
- Each phase must be completable in 1–3 days of focused work maximum.
- Be specific: name the actual files, endpoints, or components that get built.
"""


def implementation_agent(state: PlannerState) -> PlannerState:
    """Generate ImplementationPlan.md from PRD + TRD + Schema."""
    ctx = load_context(state, "PRD.md", "TRD.md", "Schema.md")

    prd_content = ctx.get("PRD.md", "").strip()
    trd_content = ctx.get("TRD.md", "").strip()
    schema_content = ctx.get("Schema.md", "").strip()

    if not prd_content and not trd_content:
        state.pending_questions = ["PRD.md and TRD.md are empty. Cannot generate implementation plan."]
        state.status = "needs_input"
        state.calling_agent = "implementation"
        return state

    user_content = ""
    if prd_content:
        user_content += f"PRD:\n{prd_content}\n"
    if trd_content:
        user_content += f"\nTRD:\n{trd_content}\n"
    if schema_content:
        user_content += f"\nSchema:\n{schema_content}\n"
    if state.grill_answers:
        user_content += "\nAdditional context from user:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "ImplementationPlan.md")
    if update_inst:
        user_content += update_inst

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "ImplementationPlan.md", content)

    state.current_file = "ImplementationPlan.md"
    state.status = "drafting"
    state.next_agent = "tracker"
    return state
