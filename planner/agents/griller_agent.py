"""
griller_agent.py — Interactive CLI griller that collects answers for pending_questions.
"""
from planner.state import PlannerState


def griller_agent(state: PlannerState) -> PlannerState:
    """
    Prompt user for the first pending question.
    Typing '?' indicates we need a tech stack expert suggestion.
    """
    if not state.pending_questions:
        state.status = "drafting"
        state.next_agent = state.calling_agent or "orchestrator"
        return state

    from pathlib import Path
    from planner.tools.tracker_tools import update_file_status
    project_root = str(Path(state.project_path).parent)
    
    # Mark file as Blocked/Awaiting user input
    update_file_status(
        project_root,
        state.current_file,
        "❌ Blocked",
        "griller_agent",
        notes="Awaiting user input"
    )

    question = state.pending_questions[0]
    print("\n" + "=" * 60)
    print("🔍  PLANNER NEEDS MORE INFORMATION")
    print("=" * 60)
    print(f"    {question}")
    print("    (Type your answer, or '?' to get a tech stack suggestion)\n")

    try:
        answer = input("  ▶  Your answer: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSession interrupted. Aborting grilling.")
        state.status = "error"
        state.error_message = "User interrupted the grilling session."
        return state

    if answer == "?":
        # Return flag saying we need tech stack suggestion
        state.active_suggestion = {
            "question": question,
            "status": "pending"
        }
        state.status = "needs_input"
        return state

    state.grill_answers[question] = answer
    state.pending_questions.pop(0)

    if not state.pending_questions:
        state.status = "drafting"
        state.next_agent = state.calling_agent or "orchestrator"
        
        # Resume the specialist agent in the tracker status
        specialist_agent_name = f"{state.calling_agent}_agent" if state.calling_agent else "agent"
        update_file_status(
            project_root,
            state.current_file,
            "🔄 In Progress",
            specialist_agent_name,
            notes="Resumed specialist agent."
        )
        print("\n✅  All questions answered. Resuming...\n")
    else:
        state.status = "needs_input"

    return state
