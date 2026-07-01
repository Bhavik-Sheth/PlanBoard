"""
planboard/tools/ascii_tools.py — ASCII/Unicode diagram generation tools.
"""

import os
from datetime import datetime
import networkx as nx
from rich.text import Text
from rich.console import Console
from planboard.tools.exceptions import LLMCallError
from planboard.tools.llm_tools import llm_call_json, llm_call
from planboard.tools.file_tools import write_file, read_file

def build_graph_from_description(description: dict) -> nx.DiGraph:
    """
    Takes a structured dict describing nodes + edges and returns a networkx.DiGraph.
    """
    G = nx.DiGraph()
    nodes = description.get("nodes", [])
    for node in nodes:
        if isinstance(node, dict):
            name = node.get("name") or node.get("id")
            if name:
                G.add_node(name, **node)
        else:
            G.add_node(str(node))
            
    edges = description.get("edges", [])
    for edge in edges:
        u = edge.get("from") or edge.get("source")
        v = edge.get("to") or edge.get("target")
        label = edge.get("label", "")
        if u and v:
            G.add_edge(str(u), str(v), label=str(label))
            
    return G

def render_ascii_diagram(graph: nx.DiGraph, charset: str = "ascii") -> str:
    """
    Wraps PHART's ASCIIRenderer to render a networkx.DiGraph.
    Supports charset: 'ascii', 'unicode', 'ansi'.
    """
    try:
        from phart import ASCIIRenderer
        
        # Instantiate with charset handling
        try:
            renderer = ASCIIRenderer(charset=charset)
        except TypeError:
            try:
                renderer = ASCIIRenderer(mode=charset)
            except TypeError:
                try:
                    renderer = ASCIIRenderer()
                    renderer.charset = charset
                except Exception:
                    renderer = ASCIIRenderer()
                    
        return str(renderer.render(graph))
    except Exception as exc:
        # If PHART import or rendering fails, we raise an exception so the pipeline can fall back
        raise RuntimeError(f"PHART rendering failed: {exc}")

def generate_diagram_from_files(diagram_type: str, context_files: dict[str, str], charset: str = "ascii") -> str:
    """
    Reads file contents -> LLM extracts graph structure -> build_graph -> render_ascii_diagram.
    Falls back to LLM fallback ASCII generation if PHART rendering fails.
    """
    context_str = "\n\n".join(f"=== File: {name} ===\n{content}" for name, content in context_files.items())
    
    prompt = f"""You are a software architect. Read the file contents below and extract the structure of a diagram representing the system.
Specifically, we want to construct a {diagram_type} diagram.

Analyze the text and extract all key entities (nodes) and their relationships (edges with labels).
Produce a JSON object with the exact keys:
"nodes": [list of string node names]
"edges": [list of objects containing "from", "to", and "label" string fields]

File contents context:
{context_str}
"""
    
    try:
        # Call LLM to extract JSON structure
        description = llm_call_json(prompt, system="You only output valid JSON representing nodes and edges of a graph.")
        # Build graph
        G = build_graph_from_description(description)
        # Render ASCII
        return render_ascii_diagram(G, charset=charset)
    except Exception as exc:
        # Fallback to LLM fallback text renderer
        return render_ascii_fallback(diagram_type, context_str)

def render_ascii_fallback(diagram_type: str, context: str) -> str:
    """
    LLM fallback for generating diagram directly using box-drawing characters.
    """
    prompt = f"""You are a technical designer. Draw a {diagram_type} diagram directly using ASCII/Unicode box-drawing characters (+, -, |, >, v, ^).
Ensure the diagram fits within 80 characters wide, has clear flows, and is readable in any terminal.

File contents context:
{context}

Draw the diagram and output ONLY the plain text diagram. Do not wrap the output in markdown code fences or add commentary.
"""
    try:
        return llm_call(prompt, system="You are an ASCII artist that outputs raw diagrams without markdown code fences.")
    except Exception as exc:
        return f"[Error generating diagram fallback: {exc}]"

def write_ascii_diagram(path: str, content: str, diagram_type: str) -> bool:
    """
    Writes ASCII diagram string to ARCHITECTURE_DIAGRAMS/<filename>.md.
    Prepends metadata header.
    On failure: prepends [STALE — regeneration failed at HH:MM] to existing content.
    """
    abs_path = os.path.abspath(path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    header = f"<!-- Generated: {now} | Type: {diagram_type} | Charset: unicode -->\n"
    new_content = header + "```\n" + content + "\n```\n"
    
    try:
        # Try writing
        return write_file(abs_path, new_content, overwrite=True)
    except Exception:
        # On failure, read existing, prepend stale tag
        existing = read_file(abs_path)
        stale_header = f"<!-- [STALE — regeneration failed at {now}] -->\n"
        fallback_content = stale_header + existing
        # Bypass write_file directly to prevent recursive failures if it's RawIdea.md
        tmp_path = abs_path + ".tmp"
        try:
            Path(tmp_path).write_text(fallback_content, encoding="utf-8")
            os.replace(tmp_path, abs_path)
            return False
        except Exception:
            return False

def diagram_to_rich_text(ascii_content: str) -> str:
    """
    Wraps the ASCII diagram in Rich Text with monospace formatting for TUI.
    Returns the styled ANSI string.
    """
    console = Console(force_terminal=True, color_system="truecolor")
    # Clean up markdown code block wrapping if present
    content = ascii_content
    if content.startswith("```"):
        content = "\n".join(content.splitlines()[1:])
    if content.endswith("```"):
        content = "\n".join(content.splitlines()[:-1])
        
    text = Text(content, style="green")
    with console.capture() as cap:
        console.print(text)
    return cap.get()
