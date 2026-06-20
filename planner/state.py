from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class PlannerState(BaseModel):
    """
    Shared state passed between all LangGraph nodes.
    Every agent reads this, mutates it, and returns it.
    Files on disk are the true source of truth; this is just the runtime bus.
    """
    project_path: str = Field(
        ...,
        description="Absolute path to the PLANNER/ directory.",
    )
    current_file: str = Field(
        "",
        description="Which file is currently being written, e.g. 'PRD.md'.",
    )
    structured_idea: str = Field(
        "",
        description="Cached content of StructuredIdea.md (loaded once per run).",
    )
    context_files: Dict[str, str] = Field(
        default_factory=dict,
        description="filename -> content cache, loaded from disk on demand by agents.",
    )
    pending_questions: List[str] = Field(
        default_factory=list,
        description="Questions set by a specialist agent when it needs clarification.",
    )
    grill_answers: Dict[str, str] = Field(
        default_factory=dict,
        description="question -> answer, filled by the Griller agent after prompting user.",
    )
    tech_suggestions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Suggestions from the TechStackExpert agent, keyed by question.",
    )
    status: str = Field(
        "drafting",
        description="Workflow status: 'drafting' | 'needs_input' | 'approved' | 'done' | 'error'.",
    )
    next_agent: str = Field(
        "",
        description="The next agent node the orchestrator (or griller) wants to route to.",
    )
    calling_agent: str = Field(
        "",
        description="Tracks which specialist last routed to the Griller, so Griller can route back.",
    )
    has_frontend: bool = Field(
        True,
        description="Whether the project has a frontend. False skips DesignDecisions/AppFlow agents.",
    )
    approved_files: List[str] = Field(
        default_factory=list,
        description="Filenames that have been explicitly approved by the user.",
    )
    error_message: str = Field(
        "",
        description="Last error message from a failed LLM call, for display to the user.",
    )
