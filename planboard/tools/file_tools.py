"""
planboard/tools/file_tools.py — File manipulation and scaffolding tools.
"""

import os
import shutil
import re
from pathlib import Path
from planboard.tools.exceptions import OverwriteProtectionError, ReadOnlyFileError

# Session cache: path_str -> content_str
_READ_CACHE: dict[str, str] = {}

def read_file(path: str) -> str:
    """
    Reads a file from PLANBOARD/ (or any path) and returns its content as a string.
    Returns empty string "" if file doesn't exist — never raises on missing file.
    Caches read in session memory to avoid repeated disk reads.
    """
    abs_path = os.path.abspath(path)
    if abs_path in _READ_CACHE:
        return _READ_CACHE[abs_path]
    
    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        _READ_CACHE[abs_path] = ""
        return ""
    
    try:
        content = Path(abs_path).read_text(encoding="utf-8")
        _READ_CACHE[abs_path] = content
        return content
    except Exception:
        return ""

def write_file(path: str, content: str, overwrite: bool = False) -> bool:
    """
    Writes content to file.
    If file is non-empty and overwrite=False → raises OverwriteProtectionError.
    If file is RawIdea.md → always raises ReadOnlyFileError, regardless of overwrite flag.
    Atomic write: writes to .tmp first, then renames — prevents partial writes corrupting files.
    """
    abs_path = os.path.abspath(path)
    filename = os.path.basename(abs_path)
    
    if filename == "RawIdea.md":
        raise ReadOnlyFileError("RawIdea.md is read-only. Use append_file to modify it.")
        
    # Check if file exists and is non-empty
    if os.path.exists(abs_path) and os.path.getsize(abs_path) > 0 and not overwrite:
        raise OverwriteProtectionError(f"File '{filename}' already exists and is non-empty. Set overwrite=True to force overwrite.")
        
    # Ensure parent directories exist
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
        
    # Atomic write via .tmp
    tmp_path = abs_path + ".tmp"
    try:
        Path(tmp_path).write_text(content, encoding="utf-8")
        os.replace(tmp_path, abs_path)
        
        # Invalidate read cache
        if abs_path in _READ_CACHE:
            _READ_CACHE.pop(abs_path)
            
        return True
    except Exception as exc:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise exc

def append_file(path: str, content: str) -> bool:
    """
    Appends content to end of file with a trailing newline.
    Only valid operation on: RawIdea.md, DesignDecisions.md (ADR log), Tracker.md change log.
    Other files: use write_file with overwrite=True.
    """
    abs_path = os.path.abspath(path)
    filename = os.path.basename(abs_path)
    
    allowed_appends = {"RawIdea.md", "DesignDecisions.md", "Tracker.md"}
    if filename not in allowed_appends:
        raise ValueError(f"Append operation is not allowed on '{filename}'. Only {allowed_appends} can be appended to.")
        
    # Ensure parent directories exist
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
        
    # Read existing content first to handle spacing correctly
    existing = ""
    if os.path.exists(abs_path):
        existing = Path(abs_path).read_text(encoding="utf-8")
        
    # Ensure content has a trailing newline
    formatted_content = content
    if not formatted_content.endswith("\n"):
        formatted_content += "\n"
        
    # Add separating newline if existing content doesn't end with one
    separator = ""
    if existing and not existing.endswith("\n") and not formatted_content.startswith("\n"):
        separator = "\n"
        
    new_content = existing + separator + formatted_content
    
    # Write atomically
    tmp_path = abs_path + ".tmp"
    try:
        Path(tmp_path).write_text(new_content, encoding="utf-8")
        os.replace(tmp_path, abs_path)
        
        # Invalidate read cache
        if abs_path in _READ_CACHE:
            _READ_CACHE.pop(abs_path)
            
        return True
    except Exception as exc:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise exc

PLANBOARD_FILES = [
    "RawIdea.md",
    "Constraints.md",
    "StructuredIdea.md",
    "PRD.md",
    "TRD.md",
    "DesignDecisions.md",
    "AppFlow.md",
    "Schema.md",
    "ImplementationPlan.md",
    "Tracker.md",
    "Rules.md",
    "CLAUDE.md",
]

DIAGRAM_FILES = [
    "SystemDesign.md",
    "SystemArchitecture.md",
    "FolderStructure.md",
    "DataFlow.md",
]

def scaffold_planboard(project_path: str) -> list[str]:
    """
    Creates PLANBOARD/ directory + all required empty .md files.
    Creates ARCHITECTURE_DIAGRAMS/ and MODULES/ subdirectories.
    Returns list of paths created.
    Idempotent: if folder/file already exists, skips it without error.
    """
    root = Path(project_path)
    planboard_dir = root / "PLANBOARD"
    diagrams_dir = planboard_dir / "ARCHITECTURE_DIAGRAMS"
    modules_dir = planboard_dir / "MODULES"
    
    created_paths = []
    
    # Create directories
    for directory in (planboard_dir, diagrams_dir, modules_dir):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_paths.append(str(directory.resolve()))
            
    # Create PLANBOARD files
    for filename in PLANBOARD_FILES:
        filepath = planboard_dir / filename
        if not filepath.exists():
            filepath.touch()
            created_paths.append(str(filepath.resolve()))
            
    # Create diagram files
    for filename in DIAGRAM_FILES:
        filepath = diagrams_dir / filename
        if not filepath.exists():
            filepath.touch()
            created_paths.append(str(filepath.resolve()))
            
    return created_paths

def list_planboard_files(project_path: str) -> dict[str, dict]:
    """
    Returns all files in PLANBOARD/ with metadata: {path: {size, modified_at, is_empty}}
    The 'path' key is the relative path from the PLANBOARD/ directory (e.g. 'PRD.md').
    """
    planboard_dir = Path(project_path) / "PLANBOARD"
    result = {}
    
    if not planboard_dir.exists() or not planboard_dir.is_dir():
        return result
        
    for root, _, files in os.walk(planboard_dir):
        for file in files:
            full_path = Path(root) / file
            # Relative path from PLANBOARD/
            rel_path = str(full_path.relative_to(planboard_dir))
            
            try:
                stat = full_path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                content = full_path.read_text(encoding="utf-8") if size > 0 else ""
                is_empty = (size == 0 or not content.strip())
            except Exception:
                size = 0
                mtime = 0.0
                is_empty = True
                
            result[rel_path] = {
                "size": size,
                "modified_at": mtime,
                "is_empty": is_empty
            }
            
    return result

def file_exists(path: str) -> bool:
    """Simple existence check — wraps os.path.exists"""
    return os.path.exists(path)

def clear_file(path: str, force: bool = False) -> bool:
    """
    Empties a file (used by /reset command).
    Requires force=True parameter — prevents accidental clears.
    """
    if not force:
        raise ValueError("force=True is required to clear a file.")
        
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return False
        
    try:
        # Atomic clear
        write_file(abs_path, "", overwrite=True)
        return True
    except ReadOnlyFileError:
        # If it's RawIdea.md which raises ReadOnlyFileError from write_file,
        # we bypass write_file and clear it directly.
        tmp_path = abs_path + ".tmp"
        Path(tmp_path).write_text("", encoding="utf-8")
        os.replace(tmp_path, abs_path)
        if abs_path in _READ_CACHE:
            _READ_CACHE.pop(abs_path)
        return True
    except Exception as exc:
        raise exc

def read_section(path: str, heading: str) -> str:
    """
    Reads a specific ##/### section from a markdown file by heading name.
    Returns empty string if heading not found.
    """
    content = read_file(path)
    if not content:
        return ""
        
    # Normalize input heading pattern
    norm_target = re.sub(r'[^a-z0-9]', '', heading.lower())
    
    lines = content.splitlines()
    start_idx = -1
    target_level = -1
    
    for idx, line in enumerate(lines):
        match = re.match(r'^(#+)\s+(.*)$', line.strip())
        if match:
            level_str, heading_text = match.groups()
            norm_heading = re.sub(r'[^a-z0-9]', '', heading_text.lower())
            
            if norm_target in norm_heading:
                start_idx = idx
                target_level = len(level_str)
                break
                
    if start_idx == -1:
        return ""
        
    # Capture lines until we meet a heading of equal or higher level (fewer or equal '#'s)
    captured = []
    # Include the heading itself? The specification says "Reads a specific section from a markdown file by heading name",
    # usually it includes the content under the heading, or the heading itself and the content. Let's include the content under it.
    for line in lines[start_idx + 1:]:
        match = re.match(r'^(#+)\s+.*$', line.strip())
        if match:
            level = len(match.group(1))
            if level <= target_level:
                break
        captured.append(line)
        
    return "\n".join(captured).strip()
