"""
planboard/tools/editor_tools.py — File editing subprocess tools.
"""

import os
import subprocess
from pathlib import Path

def detect_editor() -> str:
    """
    Returns the editor that will be used: reads $EDITOR, $VISUAL, falls back to 'nano'.
    """
    return os.getenv("EDITOR") or os.getenv("VISUAL") or "nano"

def open_in_editor(path: str) -> str:
    """
    Opens file at path in $EDITOR (falls back to nano if unset).
    Blocks until editor process exits.
    Returns updated file content after editor closes.
    """
    editor = detect_editor()
    abs_path = os.path.abspath(path)
    
    # Ensure parent directories exist
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
        
    # Ensure file exists
    if not os.path.exists(abs_path):
        Path(abs_path).touch()
        
    # Run the editor process synchronously
    try:
        subprocess.run([editor, abs_path], check=True)
    except Exception as exc:
        # Fall back to nano if the custom editor failed to launch
        if editor != "nano":
            try:
                subprocess.run(["nano", abs_path], check=True)
            except Exception as nested_exc:
                raise RuntimeError(f"Failed to open editor '{editor}' or fallback 'nano': {nested_exc}") from exc
        else:
            raise RuntimeError(f"Failed to open editor 'nano': {exc}")
            
    # Read the file content
    return Path(abs_path).read_text(encoding="utf-8")
