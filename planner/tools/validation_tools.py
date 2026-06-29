"""
planner/tools/validation_tools.py — File validation and consistency check tools.
"""

import os
import re
from planner.tools.file_tools import read_file
from planner.tools.llm_tools import llm_call_json

# Frontend keywords used for signal detection
FRONTEND_KEYWORDS = {
    "frontend", "front-end", "ui", "ux", "web app", "webapp",
    "mobile", "react", "vue", "angular", "next.js", "nuxt",
    "flutter", "swift", "android", "ios", "html", "css",
    "dashboard", "interface", "screen", "page", "component"
}

REQUIRED_SECTIONS_MAP = {
    "StructuredIdea.md": ["Problem Statement", "Solution Overview"],
    "Constraints.md": ["Constraints"],
    "PRD.md": ["Problem Statement", "Target Users", "Core Features", "Out of Scope", "User Stories", "Success Metrics", "Edge Cases"],
    "TRD.md": ["Tech Stack", "System Architecture", "API Design", "Non-Functional", "Integrations", "Constraints"],
    "Schema.md": ["Schema"],
    "DesignDecisions.md": ["Design Decisions"],
    "AppFlow.md": ["App Flow"],
    "Rules.md": ["Rules"],
    "ImplementationPlan.md": ["Plan"],
}

def validate_file_structure(path: str, required_sections: list[str]) -> dict:
    """
    Checks that a written file contains all required ##/### headings.
    Returns {valid: bool, missing_sections: list[str], empty_sections: list[str]}
    """
    abs_path = os.path.abspath(path)
    content = read_file(abs_path)
    
    if not content:
        return {
            "valid": False,
            "missing_sections": required_sections,
            "empty_sections": []
        }
        
    lines = content.splitlines()
    
    # Parse headings and capture content positions
    headings = []
    for idx, line in enumerate(lines):
        match = re.match(r'^(#+)\s+(.*)$', line.strip())
        if match:
            level_str, heading_text = match.groups()
            headings.append({
                "level": len(level_str),
                "text": heading_text,
                "line_idx": idx
            })
            
    missing_sections = []
    empty_sections = []
    
    for req in required_sections:
        req_norm = re.sub(r'[^a-z0-9]', '', req.lower())
        found_idx = -1
        
        # Fuzzy match heading text
        for i, h in enumerate(headings):
            h_norm = re.sub(r'[^a-z0-9]', '', h["text"].lower())
            if req_norm in h_norm:
                found_idx = i
                break
                
        if found_idx == -1:
            missing_sections.append(req)
        else:
            # Check if section content is empty
            h = headings[found_idx]
            start_line = h["line_idx"] + 1
            
            # End line is the start of the next heading of equal or higher level
            end_line = len(lines)
            for next_h in headings[found_idx + 1:]:
                if next_h["level"] <= h["level"]:
                    end_line = next_h["line_idx"]
                    break
                    
            section_content = "\n".join(lines[start_line:end_line]).strip()
            
            # Filter placeholder texts
            placeholders = {
                "tbd", "to be determined", "[insert", "[todo", "todo", "tbc", 
                "none", "n/a", "not applicable", "_none recorded_"
            }
            content_clean = re.sub(r'[^a-z0-9]', '', section_content.lower())
            
            is_empty = not section_content or content_clean in placeholders
            if is_empty:
                empty_sections.append(req)
                
    valid = (len(missing_sections) == 0 and len(empty_sections) == 0)
    return {
        "valid": valid,
        "missing_sections": missing_sections,
        "empty_sections": empty_sections
    }

def check_frontend_signals(structured_idea: str, trd_content: str) -> bool:
    """
    Checks both StructuredIdea.md and TRD.md for frontend-indicating keywords.
    Returns True if frontend detected, False if backend-only.
    """
    negation_phrases = re.compile(
        r"\b(no|without|purely?|headless|backend.?only|cli.?only)\b.{0,20}"
        r"\b(frontend|ui|web|mobile|interface)\b",
        re.IGNORECASE,
    )
    
    affirmative = re.compile(
        r"\b(react|vue|angular|next\.js|nuxt|flutter|swift|android|ios|html|css|"
        r"web app|webapp|dashboard|web interface|mobile app|frontend|front.end|"
        r"user interface)\b",
        re.IGNORECASE,
    )
    
    for text in (structured_idea, trd_content):
        if not text:
            continue
        # Remove negation sentences before checking affirmatives
        text_without_negations = negation_phrases.sub("", text)
        if affirmative.search(text_without_negations):
            return True
            
    return False

def check_consistency(files: dict[str, str]) -> list[dict]:
    """
    Cross-file consistency check via LLM call.
    Takes {filename: content} dict of all PLANNER/ files.
    Returns list of {file_a, file_b, issue} dicts.
    """
    combined = ""
    for fname, content in files.items():
        if content.strip():
            combined += f"\n\n## File: {fname}\n{content.strip()}"
            
    if not combined.strip():
        return []
        
    system = """You are a technical documentation auditor. 
Analyze the provided planning documents for contradictions, mismatches, and inconsistencies.
Look for:
- Schema tables mentioned in TRD/AppFlow but not defined in Schema.md.
- Features in PRD that are missing from ImplementationPlan.md.
- Tech stack choices in TRD that conflict with Constraints.md.
- Screens in AppFlow.md not covered by PRD features.
- Rules that contradict the chosen tech stack.

Output ONLY a JSON array of objects, where each object has:
  "file_a": name of the first file
  "file_b": name of the second file
  "issue": explanation of the contradiction/mismatch
"""
    prompt = f"Planning Documents:\n{combined}"
    
    try:
        results = llm_call_json(prompt, system=system)
        if isinstance(results, list):
            return results
        return []
    except Exception:
        return []

def file_is_complete(path: str, filename: str) -> bool:
    """
    Returns True if file is non-empty AND has its required sections.
    """
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
        
    lookup_name = os.path.basename(filename)
    if lookup_name not in REQUIRED_SECTIONS_MAP:
        return True
        
    required = REQUIRED_SECTIONS_MAP[lookup_name]
    content = read_file(path)
    if not content.strip():
        return False
        
    # Check that all required sections are present
    res = validate_file_structure(path, required)
    return res["valid"]
