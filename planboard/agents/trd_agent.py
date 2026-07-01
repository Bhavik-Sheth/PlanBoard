"""
trd_agent.py — Technical Requirements Document agent.
Reads: StructuredIdea.md, PRD.md, Constraints.md
Writes: TRD.md
"""
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.state import PlannerState
from planboard.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file, get_update_instructions

SYSTEM_PROMPT = """You are a principal software architect. Your job is to write a Technical Requirements Document (TRD).

The TRD MUST cover:
1. **Tech Stack**: Frontend, backend, database, infrastructure — with specific choices and justification.
2. **System Architecture Overview**: A high-level description of how components interact (mention any mermaid diagram you'd put in a diagram file).
3. **API Design**: Key endpoints / interfaces (REST, GraphQL, CLI commands, SDK methods — whatever applies).
4. **Non-Functional Requirements**: Performance targets, security requirements, scalability approach.
5. **Third-Party Integrations**: External services, APIs, SDKs the system relies on.
6. **Technical Constraints**: Hard limits inherited from PRD, budget, platform, or team constraints.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences.
- If the project has no frontend, say so explicitly and mark frontend section as N/A.
- Be specific: name real libraries, versions where known, and explain why they were chosen.
- Inherit and respect every constraint listed in Constraints.md.
"""


def _gather(state: PlannerState) -> PlannerState:
    ctx = load_context(state, "StructuredIdea.md", "PRD.md", "Constraints.md")
    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    prd_content = ctx.get("PRD.md", "").strip()
    constraints = ctx.get("Constraints.md", "").strip()

    questions = []
    if not structured_idea:
        questions.append("StructuredIdea.md is empty. Please run `describe` first.")
    if not prd_content:
        questions.append("PRD.md is missing — cannot write TRD without it")
    if not constraints:
        questions.append("Constraints.md is missing — needed for NFR and stack decisions")

    # Check for authentication method decision if 'auth' is mentioned in the idea
    idea_lower = structured_idea.lower()
    if "auth" in idea_lower or "login" in idea_lower or "sign up" in idea_lower or "user" in idea_lower:
        has_auth_answer = False
        for q, a in state.grill_answers.items():
            if "authentication method" in q.lower() or "auth method" in q.lower() or q == "What authentication method will the app use?":
                if a.strip():
                    has_auth_answer = True
                    break
        if not has_auth_answer:
            questions.append("What authentication method will the app use?")

    state.pending_questions = questions
    if questions:
        state.status = "needs_input"
        state.calling_agent = "trd"
    else:
        state.status = "drafting"
    return state


def _write(state: PlannerState) -> PlannerState:
    ctx = load_context(state, "StructuredIdea.md", "PRD.md", "Constraints.md")

    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    prd_content = ctx.get("PRD.md", "").strip()
    constraints = ctx.get("Constraints.md", "").strip()

    user_content = f"Structured Idea:\n{structured_idea}\n"
    if prd_content:
        user_content += f"\nPRD:\n{prd_content}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"
    if state.grill_answers:
        user_content += "\nAdditional context from user:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    update_inst = get_update_instructions(state, "TRD.md")
    if update_inst:
        user_content += update_inst

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "TRD.md", content)

    state.current_file = "TRD.md"
    state.status = "drafting"
    state.next_agent = "schema"
    state.phase = "done"
    return state


def trd_agent(state: PlannerState) -> PlannerState:
    """Generate TRD.md from StructuredIdea + PRD + Constraints, using gather/write phases."""
    if state.phase == "gather":
        return _gather(state)
    elif state.phase == "write":
        return _write(state)
    return state
