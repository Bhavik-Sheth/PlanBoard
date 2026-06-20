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
    from planner.files.reader import read_planner_file

    planner_dir = Path(state.project_path)
    result: dict[str, str] = {}

    for name in filenames:
        if name in state.context_files:
            result[name] = state.context_files[name]
            continue
        path = planner_dir / name
        if path.exists():
            content = read_planner_file(path, use_cache=False)
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
    from planner.llm import get_llm

    while True:
        try:
            llm = get_llm()
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
    from planner.files.writer import write_planner_file

    path = Path(state.project_path) / filename
    write_planner_file(path, content, force=True)
