"""
planner/tools/diff_tools.py — Diffing and change summarization tools.
"""

import difflib
from planner.tools.llm_tools import llm_call

def semantic_diff(before: str, after: str) -> str:
    """
    LLM call: given two versions of a file, returns a human-readable summary of what changed.
    Not a raw git diff — returns bullet points. Max 10 bullet points.
    """
    if not before.strip() and not after.strip():
        return "- No changes (both versions are empty)."
    elif not before.strip():
        return "- File created with new content."
    elif not after.strip():
        return "- File content cleared / deleted."
        
    system = (
        "You are a technical editor. Compare the content of a file before and after an update. "
        "Produce a clean, concise bulleted list summarizing the key semantic changes (what was added, "
        "removed, or modified). Do NOT output a raw code/git diff. Be concise and human-friendly. "
        "Limit the output to a maximum of 10 bullet points."
    )
    prompt = f"Before Content:\n{before}\n\nAfter Content:\n{after}"
    
    try:
        return llm_call(prompt, system=system).strip()
    except Exception as exc:
        return f"- [Error generating semantic diff: {exc}]"

def raw_diff(before: str, after: str) -> list[str]:
    """
    Standard Python difflib.unified_diff output.
    Used internally for logging, not shown to user directly.
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    return list(difflib.unified_diff(
        before_lines, after_lines, 
        fromfile='before', tofile='after'
    ))
