"""
appflow_agent.py — App Flow / user journey agent (frontend projects only).
Reads: StructuredIdea.md, PRD.md, TRD.md
Writes: AppFlow.md
"""
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file, get_update_instructions

SYSTEM_PROMPT = """You are a UX architect and product designer. Your job is to write AppFlow.md — 
a complete user journey and navigation document for the application.

AppFlow.md MUST contain:
1. **Primary User Flows**: For each main user journey (e.g. signup, onboarding, core feature use, settings):
   - Step-by-step screen/state transitions in plain English.
   - Entry point and exit point.
2. **Mermaid Flowchart**: A `flowchart TD` Mermaid diagram for each primary flow showing the state machine.
3. **Edge Cases in Flow**: What happens when:
   - User is unauthenticated and tries to access a protected route.
   - An action fails (network error, validation error).
   - Session expires mid-flow.
4. **Navigation Map**: A hierarchical list of all screens/pages/views and how they connect.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences (except inside mermaid blocks).
- Use real screen/page names derived from the PRD feature list.
- Every flow must have a clear start and end state.
"""


def appflow_agent(state: PlannerState) -> PlannerState:
    """Generate AppFlow.md — only for projects with a frontend."""
    ctx = load_context(state, "StructuredIdea.md", "PRD.md", "TRD.md")

    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    prd_content = ctx.get("PRD.md", "").strip()
    trd_content = ctx.get("TRD.md", "").strip()

    if not structured_idea:
        state.pending_questions = ["StructuredIdea.md is empty. Cannot generate app flow."]
        state.status = "needs_input"
        state.calling_agent = "appflow"
        return state

    user_content = f"Structured Idea:\n{structured_idea}\n"
    if prd_content:
        user_content += f"\nPRD:\n{prd_content}\n"
    if trd_content:
        user_content += f"\nTRD:\n{trd_content}\n"
    if state.grill_answers:
        user_content += "\nAdditional context from user:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "AppFlow.md")
    if update_inst:
        user_content += update_inst

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "AppFlow.md", content)

    state.current_file = "AppFlow.md"
    state.status = "drafting"
    state.next_agent = "rules"
    return state
