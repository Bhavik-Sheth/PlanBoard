from pathlib import Path
from typing import Callable, Optional
from planner.files.reader import clear_cache

class OverwriteRejectedError(Exception):
    """Raised when an overwrite is attempted but rejected by confirmation or lacks force flag."""
    pass

def write_planner_file(
    filepath: Path | str, 
    content: str, 
    force: bool = False, 
    confirm_callback: Optional[Callable[[Path], bool]] = None
) -> bool:
    """
    Writes content to a planner file. Enforces non-destructive rule:
    - If filename is 'RawIdea.md', always append (never overwrite/destructive).
    - If filename is anything else:
        - If file exists, is non-empty, and force=False:
            - If confirm_callback is provided, call it. If it returns False, raise OverwriteRejectedError.
            - If no confirm_callback, raise OverwriteRejectedError.
    
    Returns:
        bool: True if file was written or appended.
    """
    path = Path(filepath)
    
    # Ensure parent directories exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Enforce append-only for RawIdea.md
    if path.name == "RawIdea.md":
        clear_cache(path)
        existing_content = ""
        if path.exists():
            existing_content = path.read_text(encoding="utf-8")
        
        separator = ""
        if existing_content and not existing_content.endswith("\n") and not content.startswith("\n"):
            separator = "\n"
        
        with open(path, "a", encoding="utf-8") as f:
            f.write(separator + content)
        return True

    # 2. For other files, check if non-empty and overwrite is attempted
    if path.exists() and path.stat().st_size > 0 and not force:
        if confirm_callback:
            if not confirm_callback(path):
                raise OverwriteRejectedError(f"Overwrite of {path.name} was rejected by user confirmation.")
        else:
            raise OverwriteRejectedError(f"Overwrite of {path.name} attempted without force=True or confirmation callback.")

    # Write content (overwrite)
    clear_cache(path)
    path.write_text(content, encoding="utf-8")
    return True
