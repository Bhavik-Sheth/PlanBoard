"""
planner/agents/_base.py

Shared utilities for all specialist agents:
  - load_context(): read files from disk into state.context_files
  - invoke_llm_safe(): wrap LLM calls with user-confirmed retry logic
  - strip_markdown_fence(): clean up LLM output
  - PlannerAbortError: raised when user declines to retry
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage

if TYPE_CHECKING:
    from planner.state import PlannerState


class PlannerAbortError(Exception):
    """Raised when the user declines to retry a failed LLM call."""


def load_context(state: "PlannerState", *filenames: str) -> dict[str, str]:
    """
    Read one or more files from disk into state.context_files (if not already cached).
    Returns a dict {filename: content} for the requested files.
    """
    from planner.tools import read_file

    planner_dir = Path(state.project_path)
    result: dict[str, str] = {}

    for name in filenames:
        if name in state.context_files:
            result[name] = state.context_files[name]
            continue
        path = planner_dir / name
        if path.exists():
            content = read_file(str(path))
            state.context_files[name] = content
            result[name] = content
        else:
            state.context_files[name] = ""
            result[name] = ""

    return result


def invoke_llm_safe(messages: list[BaseMessage]) -> str:
    """
    Invoke the configured LLM with retry-on-failure behaviour.
    On exception: print error, prompt user y/n, retry or raise PlannerAbortError.
    Returns the response content as a string.
    """
    from planner.tools import get_llm_client

    while True:
        try:
            llm = get_llm_client()
            response = llm.invoke(messages)
            return str(response.content)
        except Exception as exc:
            print(f"\n[LLM ERROR] {exc}", file=sys.stderr)
            try:
                choice = input("Retry? [y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"
            if choice != "y":
                raise PlannerAbortError(str(exc)) from exc
            print("Retrying...")


def strip_markdown_fence(text: str) -> str:
    """Remove surrounding ```markdown ... ``` or ``` ... ``` fences if present."""
    t = text.strip()
    if t.startswith("```markdown"):
        t = t[11:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def write_agent_file(state: "PlannerState", filename: str, content: str) -> None:
    """Write content to a file inside the PLANNER directory (force-overwrite for agent drafts)."""
    from planner.tools import write_file

    path = Path(state.project_path) / filename
    write_file(str(path), content, overwrite=True)


def get_update_instructions(state: "PlannerState", filename: str) -> str:
    """
    If there is a change context active for the current file, return a prompt snippet
    instructing the LLM to perform an update on the existing file instead of generating from scratch.
    """
    if not state.change_context:
        return ""

    cc = state.change_context
    # Read current file content from disk (if it exists and is not empty)
    from pathlib import Path
    filepath = Path(state.project_path) / filename
    existing_content = ""
    if filepath.exists():
        existing_content = filepath.read_text(encoding="utf-8").strip()

    if not existing_content:
        return ""

    instruction = f"""
======================================================================
UPDATE INSTRUCTIONS (CRITICAL):
We are updating this file ({filename}) to reflect a change in requirements or tech stack.
Instead of writing from scratch, you MUST update the existing content below to apply the change.
Ensure you preserve all other existing content, structure, and details that are unaffected by this change.

Current File Content:
\"\"\"
{existing_content}
\"\"\"

Change Summary:
- Change Type: {cc.get('change_type', 'N/A')}
- What Changed: {cc.get('what_changed', 'N/A')}
- What was before: {cc.get('what_was_before', 'N/A')}
- Impact on this file: {cc.get('impact_on_this_file', 'N/A')}

Modify the content above to implement the required changes. Return the full, updated document.
======================================================================
"""
    return instruction
