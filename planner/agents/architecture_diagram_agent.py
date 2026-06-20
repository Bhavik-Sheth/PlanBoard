from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from planner.agents._base import invoke_llm_safe

DIAGRAM_SYSTEM_PROMPT = """You are an expert Software Architect AI.
Your job is to generate architecture diagram files for a project based on the technical context provided (TRD, Schema, AppFlow).

You must output exactly four sections, separated by headers on their own lines:
- ---SYSTEM_DESIGN---
- ---SYSTEM_ARCHITECTURE---
- ---FOLDER_STRUCTURE---
- ---DATA_FLOW---

Specifications for each section:
1. **SystemDesign.mmd**: A Mermaid sequence diagram, class diagram, or state diagram showing the core design patterns or system interactions. Do NOT wrap it in ```mermaid code block backticks. Start writing the Mermaid syntax directly.
2. **SystemArchitecture.mmd**: A Mermaid flowchart showing the high-level system architecture, components, and their connections. Do NOT wrap it in ```mermaid code block backticks. Start writing the Mermaid syntax directly.
3. **FolderStructure.md**: A Markdown document showing the proposed/actual project folder structure with clear descriptions for each directory/file. Do NOT wrap it in ```markdown code block backticks.
4. **DataFlow.md**: A Markdown document detailing how data flows through the system, including a Mermaid flowchart of key data flows. Do NOT wrap it in ```markdown code block backticks.

Rules:
- Make sure all Mermaid diagrams are syntactically valid and start with the appropriate diagram type keyword (e.g. `graph TD`, `flowchart TD`, `sequenceDiagram`, `classDiagram`).
- Write high-quality, professional architectures. If any input files are empty, make reasonable assumptions based on the parts that are filled.
- Do NOT output any conversational text or wrapping markdown code fences outside the sections. Output the headers exactly as specified (e.g. `---SYSTEM_DESIGN---`) on their own lines.
"""

def parse_diagram_output(text: str) -> dict[str, str]:
    sections = {
        "SystemDesign.mmd": "",
        "SystemArchitecture.mmd": "",
        "FolderStructure.md": "",
        "DataFlow.md": "",
    }
    
    current_key = None
    lines = text.splitlines()
    section_content = []
    
    for line in lines:
        stripped = line.strip()
        if stripped == "---SYSTEM_DESIGN---":
            if current_key and section_content:
                sections[current_key] = "\n".join(section_content).strip()
            current_key = "SystemDesign.mmd"
            section_content = []
        elif stripped == "---SYSTEM_ARCHITECTURE---":
            if current_key and section_content:
                sections[current_key] = "\n".join(section_content).strip()
            current_key = "SystemArchitecture.mmd"
            section_content = []
        elif stripped == "---FOLDER_STRUCTURE---":
            if current_key and section_content:
                sections[current_key] = "\n".join(section_content).strip()
            current_key = "FolderStructure.md"
            section_content = []
        elif stripped == "---DATA_FLOW---":
            if current_key and section_content:
                sections[current_key] = "\n".join(section_content).strip()
            current_key = "DataFlow.md"
            section_content = []
        else:
            if current_key is not None:
                section_content.append(line)
                
    if current_key and section_content:
        sections[current_key] = "\n".join(section_content).strip()
        
    # Post-process to strip fences
    for key, val in sections.items():
        val = val.strip()
        lines_val = val.splitlines()
        if lines_val:
            if lines_val[0].strip().startswith("```"):
                lines_val = lines_val[1:]
            if lines_val and lines_val[-1].strip().startswith("```"):
                lines_val = lines_val[:-1]
        sections[key] = "\n".join(lines_val).strip()
        
    return sections

def generate_diagrams(planner_path: str) -> None:
    """
    Architecture Diagram Agent logic:
    Reads TRD.md, Schema.md, AppFlow.md from planner_path.
    If all are missing/empty, exits early.
    Otherwise, invokes LLM to generate diagram files and writes them to ARCHITECTURE_DIAGRAMS/.
    """
    planner_dir = Path(planner_path)
    trd_path = planner_dir / "TRD.md"
    schema_path = planner_dir / "Schema.md"
    appflow_path = planner_dir / "AppFlow.md"
    
    trd_content = trd_path.read_text(encoding="utf-8").strip() if trd_path.exists() else ""
    schema_content = schema_path.read_text(encoding="utf-8").strip() if schema_path.exists() else ""
    appflow_content = appflow_path.read_text(encoding="utf-8").strip() if appflow_path.exists() else ""
    
    if not (trd_content or schema_content or appflow_content):
        return
        
    user_content = f"""Inputs:

TRD.md:
{trd_content or "(Empty)"}

Schema.md:
{schema_content or "(Empty)"}

AppFlow.md:
{appflow_content or "(Empty)"}
"""

    messages = [
        SystemMessage(content=DIAGRAM_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]
    
    response_text = invoke_llm_safe(messages)
    sections = parse_diagram_output(response_text)
    
    diagrams_dir = planner_dir / "ARCHITECTURE_DIAGRAMS"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    
    for filename, content in sections.items():
        if content:
            filepath = diagrams_dir / filename
            filepath.write_text(content, encoding="utf-8")
