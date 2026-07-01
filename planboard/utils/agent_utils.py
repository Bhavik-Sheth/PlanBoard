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
    Given a filename (which might be a pure filename or already include a prefix),
    resolve it to the correct relative path from planboard_path.
    Returns the resolved filename if it exists, or the original filename if it cannot be resolved.
    """
    p_path = Path(planboard_path)
    filename = filename.strip()
    if not filename:
        return None

    # Normalize separators
    filename = filename.replace("\\", "/")

    # 1. Check if the path as given exists directly
    if (p_path / filename).exists():
        return filename

    # 2. Check if it's a known top-level planning file
    pure_name = filename.split("/")[-1]
    if pure_name in _FILE_AGENT_MAP:
        if (p_path / pure_name).exists():
            return pure_name

    # 3. Check in MODULES/ directory
    modules_dir = p_path / "MODULES"
    if modules_dir.exists():
        if (modules_dir / pure_name).exists():
            return f"MODULES/{pure_name}"

    # 4. Check in ARCHITECTURE_DIAGRAMS/ directory
    diagrams_dir = p_path / "ARCHITECTURE_DIAGRAMS"
    if diagrams_dir.exists():
        if (diagrams_dir / pure_name).exists():
            return f"ARCHITECTURE_DIAGRAMS/{pure_name}"

    # 5. Fallback: search recursively for the first matching filename in the planboard directory
    try:
        for p in p_path.rglob("*.md"):
            if p.name.lower() == pure_name.lower():
                return str(p.relative_to(p_path))
    except Exception:
        pass

    # If it still doesn't exist but matches a known top-level pattern, return it as-is
    if pure_name in _FILE_AGENT_MAP:
        return pure_name

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
