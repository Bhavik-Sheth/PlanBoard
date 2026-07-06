"""
planboard/agents/update_learnings_agent.py

Agent responsible for extracting general preferences/learnings from user feedback
and updating the global learnings.md file inside ~/.planboard/skills/.
"""
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.state import PlannerState
from planboard.agents._base import invoke_llm_safe

EXTRACT_SYSTEM_PROMPT = """You are an AI developer assistant that extracts global user preferences, rules, or learnings from a user's requirements feedback/correction.
Analyze the user's request and determine if it represents a general preference, coding style, architectural rule, or stack selection that should be remembered globally (e.g., "prefer PostgreSQL", "use snake_case", "include security sections in all specs"), or if it is just a project-specific feature request or typo fix (e.g., "change app title to MyApp", "add login button").

If it is a general preference or learning, output it as one or more clear, concise markdown bullet points.
If it is project-specific or holds no general learnings, output absolutely nothing (empty response).
"""

MERGE_SYSTEM_PROMPT = """You are an AI assistant tasked with updating a list of global user preferences and learnings.
Given the existing list of preferences and a list of new learnings, merge them cleanly:
1. Deduplicate similar entries.
2. Group or consolidate overlapping points.
3. Keep the list concise and formatted as markdown bullet points under a single H1 header `# Global Learnings and Preferences`.

Existing preferences:
\"\"\"
{existing_content}
\"\"\"

New learnings to merge:
\"\"\"
{new_learnings}
\"\"\"

Output the complete merged markdown file. Do NOT wrap in code fences.
"""

class UpdateLearningsAgent:
    def __init__(self, state: PlannerState = None):
        self.state = state
        self.learnings_dir = Path.home() / ".planboard" / "skills"
        self.learnings_path = self.learnings_dir / "learnings.md"

    def run(self, target_file: str, feedback: str) -> None:
        """Extract learnings from user feedback and merge them into learnings.md."""
        # 1. Extract learning
        messages = [
            SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=f"Target file: {target_file}\nFeedback/Correction:\n{feedback}")
        ]
        
        extracted = invoke_llm_safe(messages).strip()
        if not extracted or not extracted.startswith("-"):
            # No general learnings extracted
            return

        # Ensure directory exists
        self.learnings_dir.mkdir(parents=True, exist_ok=True)

        existing_content = ""
        if self.learnings_path.exists():
            existing_content = self.learnings_path.read_text(encoding="utf-8").strip()

        # If file is empty, write initial header and learnings
        if not existing_content:
            initial_content = f"# Global Learnings and Preferences\n\n{extracted}\n"
            self.learnings_path.write_text(initial_content, encoding="utf-8")
            return

        # 2. Merge learnings
        merge_messages = [
            SystemMessage(content=MERGE_SYSTEM_PROMPT.format(
                existing_content=existing_content,
                new_learnings=extracted
            )),
            HumanMessage(content="Consolidate and merge these learnings cleanly.")
        ]
        
        from planboard.agents._base import strip_markdown_fence
        merged_content = strip_markdown_fence(invoke_llm_safe(merge_messages)).strip()
        
        self.learnings_path.write_text(merged_content + "\n", encoding="utf-8")
