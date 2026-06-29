"""
planner/tools/mermaid_tools.py — Mermaid diagram generation and syntax highlighting tools.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from rich.syntax import Syntax
from rich.console import Console
from planner.tools.exceptions import LLMCallError
from planner.tools.llm_tools import llm_call
from planner.tools.file_tools import write_file, read_file

def generate_mermaid(diagram_type: str, context: dict) -> str:
    """
    LLM call that generates a mermaid diagram string.
    diagram_type: 'flowchart' | 'erDiagram' | 'sequenceDiagram' | 'architecture'
    Returns raw mermaid string (no fences).
    """
    context_str = "\n\n".join(f"=== File: {name} ===\n{content}" for name, content in context.items())
    
    prompt = f"""You are a system architecture designer. Generate a Mermaid diagram of type '{diagram_type}' representing the system.
Use correct Mermaid syntax for the '{diagram_type}' type.
Do NOT wrap the output in markdown code fences like ```mermaid ... ```. Output the raw Mermaid graph code directly.

Context files:
{context_str}
"""
    try:
        content = llm_call(prompt, system="You only output raw Mermaid diagram syntax. Do not write explanation or code fences.")
        # Strip code fences just in case the LLM ignored the rule
        t = content.strip()
        if t.startswith("```mermaid"):
            t = t[10:]
        elif t.startswith("```"):
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
        return t.strip()
    except Exception as exc:
        raise LLMCallError(f"Failed to generate Mermaid diagram: {exc}")

def render_mermaid_to_text(mmd_content: str) -> str:
    """
    Converts .mmd content to syntax-highlighted Rich text for display in TUI.
    Returns the ANSI colored string.
    """
    console = Console(force_terminal=True, color_system="truecolor")
    syntax = Syntax(mmd_content, "mermaid", theme="monokai", word_wrap=False)
    with console.capture() as cap:
        console.print(syntax)
    return cap.get()

def write_diagram(path: str, mmd_content: str) -> bool:
    """
    Writes .mmd string to a file in ARCHITECTURE_DIAGRAMS/.
    Prepends a %% [Generated: YYYY-MM-DD HH:MM] %% comment header.
    On failure: prepends %% [STALE — regeneration failed at HH:MM] %% to existing file content.
    """
    abs_path = os.path.abspath(path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"%% [Generated: {now}] %%\n"
    new_content = header + mmd_content
    
    try:
        return write_file(abs_path, new_content, overwrite=True)
    except Exception:
        existing = read_file(abs_path)
        stale_header = f"%% [STALE — regeneration failed at {now}] %%\n"
        fallback_content = stale_header + existing
        tmp_path = abs_path + ".tmp"
        try:
            Path(tmp_path).write_text(fallback_content, encoding="utf-8")
            os.replace(tmp_path, abs_path)
            return False
        except Exception:
            return False

def validate_mermaid(mmd_content: str) -> bool:
    """
    Basic structural validation: checks for valid diagram type declaration, no unclosed brackets.
    """
    content = mmd_content.strip()
    if not content:
        return False
        
    # Strip comments to do accurate checks
    lines = []
    for line in content.splitlines():
        line_clean = re.sub(r'%%.*$', '', line).strip()
        if line_clean:
            lines.append(line_clean)
            
    if not lines:
        return False
        
    # Check for valid diagram declaration in the first non-comment line
    first_line = lines[0].lower()
    valid_starts = {
        "graph", "flowchart", "erdiagram", "sequencediagram", 
        "classdiagram", "statediagram", "statediagram-v2", 
        "gantt", "pie", "gitgraph", "c4context"
    }
    
    declared_type = first_line.split()[0]
    if declared_type not in valid_starts:
        return False
        
    # Check for unclosed brackets
    stack = []
    brackets = {')': '(', ']': '[', '}': '{'}
    
    # We will search characters
    full_text = "\n".join(lines)
    for char in full_text:
        if char in brackets.values():
            stack.append(char)
        elif char in brackets.keys():
            if not stack or stack[-1] != brackets[char]:
                return False
            stack.pop()
            
    return len(stack) == 0
