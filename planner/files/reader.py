from pathlib import Path

# Cache dictionary storing: path -> (mtime, content)
_FILE_CACHE = {}

def read_planner_file(filepath: Path | str, use_cache: bool = True) -> str:
    """
    Safely reads a markdown file from PLANNER/ with mtime-based caching.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if use_cache:
        try:
            mtime = path.stat().st_mtime
            if path in _FILE_CACHE:
                cached_mtime, cached_content = _FILE_CACHE[path]
                if cached_mtime == mtime:
                    return cached_content
        except OSError:
            # Fallback in case of permission or OS issues reading stats
            pass

    # Read from disk
    content = path.read_text(encoding="utf-8")
    
    if use_cache:
        try:
            mtime = path.stat().st_mtime
            _FILE_CACHE[path] = (mtime, content)
        except OSError:
            pass

    return content

def clear_cache(filepath: Path | str | None = None) -> None:
    """
    Clears the read cache for a specific file or the entire cache.
    """
    global _FILE_CACHE
    if filepath is None:
        _FILE_CACHE.clear()
    else:
        path = Path(filepath)
        _FILE_CACHE.pop(path, None)
