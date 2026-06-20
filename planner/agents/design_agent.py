"""
design_agent.py — Design Decisions agent (frontend projects only).
Reads: StructuredIdea.md, TRD.md, PRD.md
Writes: DesignDecisions.md
"""
from datetime import date
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file

SYSTEM_PROMPT = """You are a principal software architect specialising in architectural decision records (ADRs).
Your job is to write DesignDecisions.md — a log of key architectural choices made for this project.

The file MUST contain:
1. **Key Architectural Choices**: For each major decision (framework choice, state management, auth approach, 
   data layer design, etc.):
   - Decision: what was chosen.
   - Rationale: why this over alternatives (\"X over Y because...\").
   - Trade-offs accepted: what downsides come with this choice.
2. **Rejected Alternatives**: Technologies/approaches that were considered and why they were rejected.
3. **Decisions Log** (append-only): A table with columns: Date | Decision | Rationale | Author.
   Populate with today's date for all initial decisions.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- Be opinionated and specific. Vague rationales like \"it's popular\" are not acceptable.
- Today's date for the log: {today}
"""


def design_agent(state: PlannerState) -> PlannerState:
    """Generate DesignDecisions.md — only for projects with a frontend."""
    ctx = load_context(state, "StructuredIdea.md", "TRD.md", "PRD.md")

    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    trd_content = ctx.get("TRD.md", "").strip()
    prd_content = ctx.get("PRD.md", "").strip()

    if not structured_idea:
        state.pending_questions = ["StructuredIdea.md is empty. Cannot generate design decisions."]
        state.status = "needs_input"
        state.calling_agent = "design"
        return state

    today = date.today().isoformat()
    system = SYSTEM_PROMPT.format(today=today)

    user_content = f"Structured Idea:\n{structured_idea}\n"
    if trd_content:
        user_content += f"\nTRD:\n{trd_content}\n"
    if prd_content:
        user_content += f"\nPRD:\n{prd_content}\n"
    if state.grill_answers:
        user_content += "\nAdditional context from user:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    messages = [SystemMessage(content=system), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "DesignDecisions.md", content)

    state.current_file = "DesignDecisions.md"
    state.status = "drafting"
    state.next_agent = "appflow"
    return state
