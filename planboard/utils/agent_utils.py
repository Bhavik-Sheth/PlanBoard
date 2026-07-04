import os
from pathlib import Path

# Mapping of top-level planning files to their owning agent name
_FILE_AGENT_MAP = {
    "StructuredIdea.md":     "structuring",
    "Constraints.md":        "constraints",
    "PRD.md":                "prd",
    "TRD.md":                "trd",
    "Schema.md":             "schema",
    "DesignDecisions.md":    "design",
    "AppFlow.md":            "appflow",
    "Rules.md":              "rules",
    "ImplementationPlan.md": "implementation",
    "Tracker.md":            "tracker",
}

def resolve_relative_path(planboard_path: Path | str, filename: str) -> str | None:
    """
    Given a filename (which might be a pure filename, include a prefix,
    or be a fuzzy name/description), resolve it to the correct relative path from planboard_path.
    Returns the resolved relative path if it exists, or the original filename if it cannot be resolved.
    """
    p_path = Path(planboard_path)
    filename = filename.strip()
    if not filename:
        return None

    # Normalize separators
    filename = filename.replace("\\", "/")
    filename_lower = filename.lower()

    # 1. Check if the path as given exists directly
    if (p_path / filename).exists():
        return filename

    # 2. Match known top-level files (case-insensitive, extension-optional)
    for known_file in _FILE_AGENT_MAP:
        known_lower = known_file.lower()
        if filename_lower == known_lower or filename_lower + ".md" == known_lower:
            if (p_path / known_file).exists():
                return known_file

    # 3. Check in MODULES/ directory (fuzzy substring match)
    modules_dir = p_path / "MODULES"
    if modules_dir.exists():
        for p in modules_dir.glob("*.md"):
            p_name_lower = p.name.lower()
            if filename_lower == p_name_lower or filename_lower + ".md" == p_name_lower or filename_lower in p_name_lower:
                return f"MODULES/{p.name}"

    # 4. Check in ARCHITECTURE_DIAGRAMS/ directory (fuzzy diagram/architecture matches)
    diagrams_dir = p_path / "ARCHITECTURE_DIAGRAMS"
    if diagrams_dir.exists():
        for p in diagrams_dir.glob("*.md"):
            p_name_lower = p.name.lower()
            if (filename_lower == p_name_lower or 
                filename_lower + ".md" == p_name_lower or 
                filename_lower in p_name_lower or 
                ("architecture" in filename_lower and "architecture" in p_name_lower) or
                ("design" in filename_lower and "design" in p_name_lower) or
                ("data" in filename_lower and "data" in p_name_lower) or
                ("folder" in filename_lower and "folder" in p_name_lower)):
                return f"ARCHITECTURE_DIAGRAMS/{p.name}"

    # 5. Fallback: search recursively for first case-insensitive, extension-optional, or substring match
    pure_name = filename.split("/")[-1]
    pure_name_lower = pure_name.lower()
    try:
        # Exact/extension-optional recursive match
        for p in p_path.rglob("*.md"):
            p_name_lower = p.name.lower()
            if p_name_lower == pure_name_lower or p_name_lower == pure_name_lower + ".md":
                return str(p.relative_to(p_path))
        # Substring recursive match
        for p in p_path.rglob("*.md"):
            p_name_lower = p.name.lower()
            if pure_name_lower in p_name_lower:
                return str(p.relative_to(p_path))
    except Exception:
        pass

    # If it still doesn't exist but matches a known top-level pattern, return it as-is
    for known_file in _FILE_AGENT_MAP:
        if known_file.lower() == pure_name_lower or known_file.lower() == pure_name_lower + ".md":
            return known_file

    return filename

def resolve_agent(filename: str) -> str | None:
    """Return the agent name for a given planning filename, including subdirectory prefixes."""
    filename = filename.replace("\\", "/")
    
    if filename.startswith("MODULES/"):
        return "modules"
    if filename.startswith("ARCHITECTURE_DIAGRAMS/"):
        return "diagram"
    
    pure_name = filename.split("/")[-1]
    return _FILE_AGENT_MAP.get(pure_name)
