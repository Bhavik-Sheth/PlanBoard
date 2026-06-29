"""
tech_stack_agent.py — Tech Stack Expert agent.
Given a question from the Griller, uses LLM + project context to suggest the best option.
Presents the suggestion to the user for approval, then fills grill_answers and routes back to Griller.

Reads: Constraints.md, StructuredIdea.md
Writes: Updates state grill_answers and accepted_suggestions.
"""
from typing import TypedDict
from planner.state import PlannerState
from planner.agents._base import load_context

SYSTEM_PROMPT = """You are a world-class technology consultant who gives concise, specific, 
justified technology recommendations.

Given a question about which tool/technology/library/service to use, you will output a JSON object with the following fields:
- "question": the original question being asked
- "recommendation": the specific tool or technology recommendation (concise name)
- "why": one sentence justification for the recommendation tied to a specific non-functional requirement (NFR) or constraint
- "tradeoff": what is given up or accepted by choosing this recommendation
- "alternative": next best option if the recommendation is rejected

Output ONLY valid JSON. Do not wrap in markdown code blocks.
"""


class Suggestion(TypedDict):
    question: str               # original question being answered
    recommendation: str         # what to use
    why: str                    # one sentence tied to a specific NFR or constraint
    tradeoff: str               # what is given up
    alternative: str            # next best option if rejected
    calling_agent: str          # passed through for Orchestrator routing


def run(inputs: dict) -> dict:
    """
    Returns a structured Suggestion object.
    Inputs:
      - question: str
      - constraints: str
      - structured_idea: str
      - calling_agent: str
    """
    from planner.tools.llm_tools import llm_call_json

    question = inputs["question"]
    constraints = inputs.get("constraints", "")
    structured_idea = inputs.get("structured_idea", "")
    calling_agent = inputs.get("calling_agent", "")

    user_content = f"Question: {question}\n"
    if structured_idea:
        user_content += f"\nProject Context:\n{structured_idea}\n"
    if constraints:
        user_content += f"\nConstraints:\n{constraints}\n"

    # Call LLM and get JSON
    suggestion_data = llm_call_json(user_content, system=SYSTEM_PROMPT)

    # Ensure calling_agent and question are included
    suggestion_data["calling_agent"] = calling_agent
    suggestion_data["question"] = question
    return suggestion_data


def tech_stack_agent(state: PlannerState) -> PlannerState:
    """Generate a technology suggestion for the current pending question, present it to the user (legacy wrapper)."""
    question = ""
    if state.active_suggestion:
        question = state.active_suggestion.get("question", "")
    if not question and state.pending_questions:
        question = state.pending_questions[0]

    if not question:
        # No question to answer — just go back to griller
        state.next_agent = "griller"
        return state

    ctx = load_context(state, "StructuredIdea.md", "Constraints.md")
    structured_idea = ctx.get("StructuredIdea.md", "")
    constraints = ctx.get("Constraints.md", "")

    print("\n" + "=" * 60)
    print("🤖  TECH STACK EXPERT — generating suggestion...")
    print("=" * 60)

    suggestion = run({
        "question": question,
        "constraints": constraints,
        "structured_idea": structured_idea,
        "calling_agent": state.current_file,
    })

    print(f"\n💡 Suggestion: {suggestion.get('recommendation', '')}")
    print(f"   Why: {suggestion.get('why', '')}")
    print(f"   Trade-off: {suggestion.get('tradeoff', '')}")
    if suggestion.get("alternative"):
        print(f"   Alternative if rejected: {suggestion.get('alternative', '')}\n")
    print("-" * 60)

    try:
        choice = input("Accept this suggestion? [y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "n"

    if choice == "y":
        # Store the accepted suggestion as the answer
        state.grill_answers[question] = suggestion["recommendation"]
        
        # Log to accepted_suggestions
        state.accepted_suggestions.append({
            "question": question,
            "answer": suggestion["recommendation"],
            "why": suggestion["why"],
            "alternative_rejected": suggestion["alternative"]
        })
        
        # Remove the current question from pending_questions
        if question in state.pending_questions:
            state.pending_questions.remove(question)
    else:
        # User rejected — let them type a custom answer
        try:
            custom = input("Enter your own answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            custom = ""
        if not custom:
            custom = suggestion["alternative"]
            
        state.grill_answers[question] = custom
        
        # Log to accepted_suggestions
        state.accepted_suggestions.append({
            "question": question,
            "answer": custom,
            "why": "Alternative chosen by user",
            "alternative_rejected": suggestion["recommendation"]
        })
        
        if question in state.pending_questions:
            state.pending_questions.remove(question)

    # Clean up active_suggestion
    state.active_suggestion = None

    # Route back to griller to handle any remaining questions
    state.next_agent = "griller"
    return state
