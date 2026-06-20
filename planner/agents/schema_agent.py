"""
schema_agent.py — Database / data schema agent.
Reads: StructuredIdea.md, TRD.md, Constraints.md
Writes: Schema.md
"""
from langchain_core.messages import SystemMessage, HumanMessage
from planner.state import PlannerState
from planner.agents._base import load_context, invoke_llm_safe, strip_markdown_fence, write_agent_file

SYSTEM_PROMPT = """You are a principal database architect. Your job is to write a Schema.md file 
that defines the data model for the application.

The Schema.md MUST cover:
1. **Entities / Tables**: For each entity/table:
   - Purpose: what real-world concept it represents.
   - Columns: name, data type, constraints (PK, FK, NOT NULL, UNIQUE), and business meaning.
2. **Relationships**: Foreign keys, cardinality (1:1, 1:N, M:N), and join strategies.
3. **ER Diagram**: A text-based Mermaid `erDiagram` block showing all entities and relationships.
4. **Indexing Notes**: Which columns need indexes and why (query patterns, performance).
5. **Notes on Data Storage**: If the project uses a non-relational approach (key-value, document, 
   file-based JSON, etc.) describe the data structure equivalently.

Rules:
- Write clean Markdown. Do NOT wrap the entire output in code fences except inside the mermaid block.
- If the project stores no persistent data (stateless CLI, etc.) write a brief note explaining that 
  and skip the table sections.
- Be specific: match table/field names to the features described in the TRD and idea.
"""


def schema_agent(state: PlannerState) -> PlannerState:
    """Generate Schema.md from StructuredIdea + TRD."""
    ctx = load_context(state, "StructuredIdea.md", "TRD.md", "Constraints.md")

    structured_idea = ctx.get("StructuredIdea.md", "").strip()
    trd_content = ctx.get("TRD.md", "").strip()
    constraints = ctx.get("Constraints.md", "").strip()

    if not structured_idea:
        state.pending_questions = ["StructuredIdea.md is empty. Cannot generate schema."]
        state.status = "needs_input"
        state.calling_agent = "schema"
        return state

    user_content = f"Structured Idea:\n{structured_idea}\n"
    if trd_content:
        user_content += f"\nTRD:\n{trd_content}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"
    if state.grill_answers:
        user_content += "\nAdditional context from user:\n"
        for q, a in state.grill_answers.items():
            user_content += f"- Q: {q}\n  A: {a}\n"

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]
    content = strip_markdown_fence(invoke_llm_safe(messages))
    write_agent_file(state, "Schema.md", content)

    state.current_file = "Schema.md"
    state.status = "drafting"
    # Orchestrator will decide next: design (if frontend) or rules (if backend-only)
    state.next_agent = "orchestrator"
    return state
