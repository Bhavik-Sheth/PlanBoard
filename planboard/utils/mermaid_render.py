from pathlib import Path
from rich.syntax import Syntax

def render_mermaid_file(filepath: Path) -> Syntax:
    """
    Reads a Mermaid (.mmd) file and returns a rich.syntax.Syntax object for rendering.
    """
    content = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
    return Syntax(content, "mermaid", theme="monokai", line_numbers=False)

def render_mermaid_text(content: str) -> Syntax:
    """
    Returns a rich.syntax.Syntax object for rendering a Mermaid code block.
    """
    return Syntax(content, "mermaid", theme="monokai", line_numbers=False)
