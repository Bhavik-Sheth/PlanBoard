"""
griller_agent.py — Interactive CLI griller that collects answers for pending_questions.

Flow:
  1. For each pending question, prompt the user.
  2. If the user types '?' → route to TechStackExpert (set next_agent = "tech_stack").
  3. Once all questions are answered, clear pending_questions and route back to calling_agent.
"""
import sys
from planner.state import PlannerState


def griller_agent(state: PlannerState) -> PlannerState:
    """
    Prompt user for each pending question via CLI.
    Typing '?' on any question delegates that question to the TechStackExpert.
    """
    if not state.pending_questions:
        # Nothing to ask — just resume the calling agent
        state.status = "drafting"
        state.next_agent = state.calling_agent or "orchestrator"
        return state

    print("\n" + "=" * 60)
    print("🔍  PLANNER NEEDS MORE INFORMATION")
    print("=" * 60)
    print("  (Type your answer, or '?' to get a tech stack suggestion)\n")

    answered_all = True

    for i, question in enumerate(state.pending_questions):
        print(f"  [{i+1}/{len(state.pending_questions)}] {question}")
        try:
            answer = input("  ▶  Your answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession interrupted. Aborting grilling.")
            state.status = "error"
            state.error_message = "User interrupted the grilling session."
            return state

        if answer == "?":
            # User wants a suggestion — store which question needs expert input
            # and route to tech_stack_agent. Remaining questions will be asked on return.
            state.pending_questions = state.pending_questions[i:]  # keep current + remaining
            state.tech_suggestions["__current_question__"] = question
            state.next_agent = "tech_stack"
            answered_all = False
            return state

        state.grill_answers[question] = answer

    if answered_all:
        state.pending_questions = []
        state.status = "drafting"
        state.next_agent = state.calling_agent or "orchestrator"

    print("\n✅  All questions answered. Resuming...\n")
    return state
