import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from planner.files.scaffold import scaffold_project
from planner.agents.architecture_diagram_agent import generate_diagrams, parse_diagram_output
from planner.utils.mermaid_render import render_mermaid_file, render_mermaid_text
from planner.watcher.architecture_watcher import start_watcher

def test_parse_diagram_output():
    text = """
---SYSTEM_DESIGN---
classDiagram
  ClassA <|-- ClassB
---SYSTEM_ARCHITECTURE---
graph TD
  A --> B
---FOLDER_STRUCTURE---
# Folder Structure
- src/
---DATA_FLOW---
# Data Flow
User -> System
"""
    sections = parse_diagram_output(text)
    assert sections["SystemDesign.mmd"] == "classDiagram\n  ClassA <|-- ClassB"
    assert sections["SystemArchitecture.mmd"] == "graph TD\n  A --> B"
    assert sections["FolderStructure.md"] == "# Folder Structure\n- src/"
    assert sections["DataFlow.md"] == "# Data Flow\nUser -> System"


def test_generate_diagrams_empty_inputs(tmp_path):
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    # Ensure inputs are missing/empty
    assert not (planner_dir / "TRD.md").read_text()
    
    with patch("planner.agents.architecture_diagram_agent.invoke_llm_safe") as mock_invoke:
        generate_diagrams(str(planner_dir))
        mock_invoke.assert_not_called()


@patch("planner.agents.architecture_diagram_agent.invoke_llm_safe")
def test_generate_diagrams_with_inputs(mock_invoke, tmp_path):
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    
    (planner_dir / "TRD.md").write_text("# TRD info", encoding="utf-8")
    
    llm_output = """
---SYSTEM_DESIGN---
classDiagram
  Class01 <|-- Class02
---SYSTEM_ARCHITECTURE---
flowchart TD
  Start --> Stop
---FOLDER_STRUCTURE---
- planner/
---DATA_FLOW---
Flow description
"""
    mock_invoke.return_value = llm_output
    
    generate_diagrams(str(planner_dir))
    
    mock_invoke.assert_called_once()
    
    assert (planner_dir / "ARCHITECTURE_DIAGRAMS" / "SystemDesign.mmd").read_text(encoding="utf-8") == "classDiagram\n  Class01 <|-- Class02"
    assert (planner_dir / "ARCHITECTURE_DIAGRAMS" / "SystemArchitecture.mmd").read_text(encoding="utf-8") == "flowchart TD\n  Start --> Stop"
    assert (planner_dir / "ARCHITECTURE_DIAGRAMS" / "FolderStructure.md").read_text(encoding="utf-8") == "- planner/"
    assert (planner_dir / "ARCHITECTURE_DIAGRAMS" / "DataFlow.md").read_text(encoding="utf-8") == "Flow description"


def test_mermaid_render(tmp_path):
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    sys_design_path = planner_dir / "ARCHITECTURE_DIAGRAMS" / "SystemDesign.mmd"
    sys_design_path.write_text("classDiagram\n  Class01 <|-- Class02", encoding="utf-8")
    
    from rich.syntax import Syntax
    syntax_file = render_mermaid_file(sys_design_path)
    assert isinstance(syntax_file, Syntax)
    assert syntax_file.code == "classDiagram\n  Class01 <|-- Class02"
    
    syntax_text = render_mermaid_text("graph TD\n  A --> B")
    assert isinstance(syntax_text, Syntax)
    assert syntax_text.code == "graph TD\n  A --> B"


@patch("planner.watcher.architecture_watcher.watch")
@patch("planner.watcher.architecture_watcher.generate_diagrams")
def test_watcher_ignores_non_top_level_or_non_md(mock_generate, mock_watch, tmp_path):
    scaffold_project(base_path=tmp_path)
    planner_dir = tmp_path / "PLANNER"
    
    # Configure mock watch to yield changes
    # watch yields sets of change tuples: (change_type, path)
    # Yield 1: irrelevant file change (e.g. inside subdirectories or non-md)
    # Yield 2: valid file change
    mock_watch.return_value = [
        {(1, str(planner_dir / "ARCHITECTURE_DIAGRAMS" / "SystemDesign.mmd")), (1, str(planner_dir / "Tracker.md")), (1, str(planner_dir / "somefile.txt"))},
        {(1, str(planner_dir / "TRD.md"))}
    ]
    
    start_watcher(str(planner_dir))
    
    # generate_diagrams should only be called once (for TRD.md, since the others were ignored)
    mock_generate.assert_called_once_with(str(planner_dir))
