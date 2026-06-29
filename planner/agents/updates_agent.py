"""
planner/agents/updates_agent.py

UpdatesAgent — Coordinates updates when the plan changes mid-session.
"""
from pathlib import Path
from datetime import datetime
from typing import Literal, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from planner.state import PlannerState, save_state, load_state
from planner.tools import read_file, write_file
from planner.agents._base import invoke_llm_safe, strip_markdown_fence
from planner.agents.griller_agent import griller_agent
from planner.agents.tracker_agent import tracker_agent


class ChangeSummary(BaseModel):
    """Parsed summary of the requested change."""
    change_type: Literal["scope", "stack", "schema", "constraint", "role", "feature", "other"]
    what_changed: str = Field(..., description="One sentence summarizing what specifically changed.")
    what_was_before: str = Field(..., description="One sentence summarizing what was there before.")
    what_replaces_it: str = Field(..., description="One sentence summarizing what replaces it.")
    confidence: Literal["high", "medium", "low"] = Field(..., description="Confidence level in how clearly the change is specified.")


class BlastRadiusAnalysis(BaseModel):
    """Analysis of affected files based on the dependency map."""
    affected_files: List[str] = Field(..., description="List of filenames that must be re-run in dependency order, e.g. ['PRD.md', 'TRD.md']. Only include files that exist or should exist.")
    reasoning: str = Field(..., description="Explanation of why these files are affected and others are not.")


class UpdatesAgent:
    def __init__(self, state: PlannerState):
        self.state = state
        self.planner_dir = Path(state.project_path)

    def run(self, change_description: str, triggered_by: str = "user_command") -> PlannerState:
        # Append change to pending updates queue
        if change_description not in self.state.pending_updates:
            self.state.pending_updates.append(change_description)
            save_state(self.state)

        # Reload state in case of concurrent executions
        self.state = load_state(self.state.project_path)

        # Handle concurrency: if updates are already running, exit and let the active runner handle it
        if self.state.status == "updating":
            print(f"ℹ️ Updates in progress. Queued: '{change_description}'")
            return self.state

        # Mark status as updating
        original_status = self.state.status
        self.state.status = "updating"
        save_state(self.state)

        try:
            while self.state.pending_updates:
                current_desc = self.state.pending_updates.pop(0)
                save_state(self.state)

                self._process_single_update(current_desc, triggered_by)
                
                # Reload state after processing
                self.state = load_state(self.state.project_path)
        finally:
            # Restore status
            self.state = load_state(self.state.project_path)
            self.state.status = "done" if not self.state.pending_questions else "needs_input"
            save_state(self.state)

        return self.state

    def _process_single_update(self, change_description: str, triggered_by: str) -> None:
        print(f"\n⏳ Processing update: '{change_description}'")

        # Step 1 — Ingest the change
        si_path = self.planner_dir / "StructuredIdea.md"
        structured_idea = si_path.read_text(encoding="utf-8").strip() if si_path.exists() else ""

        from planner.tools import get_llm_client
        llm = get_llm_client()
        structured_llm = llm.with_structured_output(ChangeSummary)

        system_prompt = """You are an expert product analyst. Analyze the incoming change description and the current StructuredIdea.md.
Identify:
1. The change type: scope | stack | schema | constraint | role | feature | other
2. What specifically changed in one sentence
3. What was there before (inferred from StructuredIdea.md) in one sentence
4. What replaces it (from change_description) in one sentence
5. Your confidence level (high | medium | low) in how clearly the change is specified."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"StructuredIdea.md content:\n{structured_idea}\n\nChange description:\n{change_description}")
        ]

        summary: ChangeSummary = structured_llm.invoke(messages)

        # If confidence is low, fall back to GrillerAgent
        if summary.confidence == "low":
            print("\n⚠️ Confidence in change specification is LOW. Asking clarifying questions...")
            questions = self._generate_clarifying_questions(structured_idea, change_description)
            self.state.pending_questions = questions
            self.state.calling_agent = "updates"
            save_state(self.state)

            while self.state.pending_questions:
                self.state = griller_agent(self.state)
                save_state(self.state)
                if self.state.next_agent == "tech_stack":
                    from planner.agents.tech_stack_agent import tech_stack_agent
                    self.state = tech_stack_agent(self.state)
                    save_state(self.state)

            # Re-generate summary with clarifying answers
            grill_answers_str = "\n".join(f"- Q: {q}\n  A: {a}" for q, a in self.state.grill_answers.items())
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"StructuredIdea.md content:\n{structured_idea}\n\nChange description:\n{change_description}\n\nClarifying Details:\n{grill_answers_str}")
            ]
            summary = structured_llm.invoke(messages)

        # Step 2 — Update StructuredIdea.md (In memory rewrite first)
        system_rewrite = """You are an expert product strategist.
Your task is to update the StructuredIdea.md file to incorporate the new changes.
Ensure that:
- You ONLY modify the sections affected by the change.
- You do NOT wrap the entire output in markdown code fences (i.e. do not output ```markdown ... ``` surrounding the whole document). Start writing the markdown content directly.
- The document remains professional, well-structured, and consistent."""

        rewrite_messages = [
            SystemMessage(content=system_rewrite),
            HumanMessage(content=f"Current StructuredIdea.md:\n{structured_idea}\n\nChange Summary:\n- Type: {summary.change_type}\n- What Changed: {summary.what_changed}\n- What was before: {summary.what_was_before}\n- What replaces it: {summary.what_replaces_it}")
        ]

        updated_structured_idea = strip_markdown_fence(invoke_llm_safe(rewrite_messages))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        change_log_entry = f"""

---
## Change Log
### [{now_str}] — [{summary.change_type}]
**Change:** {summary.what_changed}
**Reason:** {change_description}
**Affects:** {{affected_files_placeholder}}"""

        # Step 3 — Blast radius analysis
        existing_files = [f.name for f in self.planner_dir.glob("*.md") if f.is_file()]
        modules_dir = self.planner_dir / "MODULES"
        if modules_dir.exists():
            existing_files.extend(f"MODULES/{f.name}" for f in modules_dir.glob("*.md") if f.is_file())

        dependency_map = """
scope (features added/removed/changed)   → PRD, TRD, AppFlow (if frontend), Tracker, ImplementationPlan, MODULES/ (affected ones)
stack change                             → TRD, Schema (if DB changed), DesignDecisions, Rules, CLAUDE.md, MODULES/ (affected ones)
schema / data model                      → Schema, TRD (data section), MODULES/ (affected ones)
constraint change                        → Constraints, TRD, DesignDecisions, Rules
new/changed user role                    → PRD, AppFlow (if frontend), Schema (if role stored), Rules (if permissions logic)
frontend added/removed                   → TRD, AppFlow, DesignDecisions, ImplementationPlan
new module                               → MODULES/<name>.md (new file, not re-run of existing)
"""

        system_blast = f"""You are a systems architect. Determine which of the planning files are affected by the proposed change.
Use the following dependency map:
{dependency_map}

Only include files that exist in the project or make sense to be re-run based on the dependency map, and present them in dependency order:
Constraints.md → PRD.md → TRD.md → Schema.md → DesignDecisions.md → AppFlow.md → Rules.md → ImplementationPlan.md

If the project has no frontend (has_frontend={self.state.has_frontend}), do NOT include frontend-only files (DesignDecisions.md, AppFlow.md).
Return a structured list of affected files and reasoning."""

        messages_blast = [
            SystemMessage(content=system_blast),
            HumanMessage(content=f"Existing files: {existing_files}\n\nChange Summary:\n- Type: {summary.change_type}\n- What Changed: {summary.what_changed}")
        ]

        structured_llm_blast = llm.with_structured_output(BlastRadiusAnalysis)
        blast_analysis: BlastRadiusAnalysis = structured_llm_blast.invoke(messages_blast)

        affected = [f.strip() for f in blast_analysis.affected_files]

        # Interactively ask to proceed unless triggered by orchestrator
        proceed = True
        if triggered_by != "orchestrator":
            print(f"\n📋 Change detected: {summary.what_changed}")
            print("\nFiles that need updating:")
            for f in affected:
                print(f"  • {f}")

            all_standard_files = ["Constraints.md", "PRD.md", "TRD.md", "Schema.md", "DesignDecisions.md", "AppFlow.md", "Rules.md", "ImplementationPlan.md"]
            unchanged = [f for f in all_standard_files if f not in affected and (self.planner_dir / f).exists()]
            if unchanged:
                print("\nFiles NOT affected (unchanged):")
                for f in unchanged:
                    print(f"  • {f}")

            while True:
                choice = input("\nProceed with updates? [yes / no / show details]: ").strip().lower()
                if choice in ("no", "n"):
                    print("Updates aborted.")
                    proceed = False
                    break
                elif choice in ("yes", "y"):
                    proceed = True
                    break
                elif "detail" in choice or choice == "d" or choice == "show":
                    print("\nChange Summary Details:")
                    print(f"  Type:                  {summary.change_type}")
                    print(f"  What changed:          {summary.what_changed}")
                    print(f"  What was there before: {summary.what_was_before}")
                    print(f"  What replaces it:      {summary.what_replaces_it}")
                    print(f"\nReasoning for affected files:\n{blast_analysis.reasoning}")
                else:
                    print("Invalid choice. Please type 'yes', 'no', or 'show details'.")

        if not proceed:
            return

        # Append log and write StructuredIdea.md to disk
        affected_files_str = ", ".join(affected)
        change_log_entry = change_log_entry.replace("{affected_files_placeholder}", affected_files_str)
        updated_structured_idea += change_log_entry
        si_path.write_text(updated_structured_idea, encoding="utf-8")
        self.state.structured_idea = updated_structured_idea

        # Remove affected files from approved list
        self.state.approved_files = [f for f in self.state.approved_files if f not in affected]
        save_state(self.state)
        print("✅ StructuredIdea.md updated on disk.")

        # Step 4 & 5 — Re-run specialist agents in dependency order & Per-file approval gate
        for filename in affected:
            target_path = self.planner_dir / filename
            agent_fn = self._get_agent_fn(filename)
            if not agent_fn:
                print(f"[WARN] No agent found for {filename}, skipping.")
                continue

            # Skip if file is pending (doesn't exist or is empty)
            if not target_path.exists() or target_path.stat().st_size == 0:
                print(f"⏳ {filename} is still Pending/empty. Skipping update re-run.")
                continue

            # Setup module details if it's modules agent
            if filename.startswith("MODULES/"):
                module_name = filename.split("/")[-1].replace(".md", "")
                self.state.context_files["__module_name__"] = module_name

            # Generate target-specific change context
            print(f"⏳ Generating impact context for {filename}...")
            content_before = target_path.read_text(encoding="utf-8").strip()
            impact = self._generate_impact_context(filename, summary, content_before)

            self.state.change_context = {
                "change_type": summary.change_type,
                "what_changed": summary.what_changed,
                "what_was_before": summary.what_was_before,
                "impact_on_this_file": impact
            }
            save_state(self.state)

            while True:
                content_before = target_path.read_text(encoding="utf-8").strip() if target_path.exists() else ""
                
                print(f"⏳ Updating {filename}...")
                self.state = agent_fn(self.state)
                save_state(self.state)
                
                content_after = target_path.read_text(encoding="utf-8").strip() if target_path.exists() else ""

                # Generate semantic diff
                diff_summary = self._generate_semantic_diff(filename, content_before, content_after)
                print(f"\n✅ {filename} updated.")
                print("\nChanges made:")
                print(diff_summary)
                print(f"\nType /approve {filename} to accept, or describe further changes.\n")

                try:
                    user_input = input("  ▶  ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("Interrupted during approval. Aborting updates.")
                    self.state.status = "error"
                    self.state.error_message = "User interrupted during file approval."
                    save_state(self.state)
                    return

                if user_input.startswith("/approve") or user_input.lower() in ("approve", "yes", "y"):
                    if filename not in self.state.approved_files:
                        self.state.approved_files.append(filename)
                    # Clear change_context and save
                    self.state.change_context = {}
                    save_state(self.state)
                    break
                else:
                    print(f"🔄 Re-running {filename} with feedback: {user_input}")
                    self.state.grill_answers[f"Change request for {filename}"] = user_input
                    save_state(self.state)

        # Step 6 — Tracker update
        tracker_agent(self.state)
        
        # Append change history to Tracker.md
        tracker_path = self.planner_dir / "Tracker.md"
        if tracker_path.exists():
            tracker_content = tracker_path.read_text(encoding="utf-8")
            log_header = "\n## Change Log\n"
            if log_header not in tracker_content:
                tracker_content += log_header
            tracker_content += f"\n- **[{now_str}]** Re-ran: {affected_files_str} | Triggered by: '{change_description}'\n"
            tracker_path.write_text(tracker_content, encoding="utf-8")

        # Update has_frontend flag if it changed
        from planner.agents.orchestrator import _detect_frontend
        old_has_frontend = self.state.has_frontend
        new_has_frontend = _detect_frontend(self.state)
        if old_has_frontend != new_has_frontend:
            self.state.has_frontend = new_has_frontend
            save_state(self.state)
            print(f"ℹ️ Project frontend status changed to {new_has_frontend}.")
            tracker_agent(self.state)

        # Step 7 — CLAUDE.md invalidation check
        claude_path = self.planner_dir.parent / "CLAUDE.md"
        if claude_path.exists():
            print("\n⚠️  CLAUDE.md exists from a previous /finalize.")
            print("    It may now be out of date due to these changes.")
            print("    Re-run /finalize after approving all updates to regenerate it.\n")

    def _get_agent_fn(self, filename: str):
        from planner.utils import resolve_agent
        agent_name = resolve_agent(filename)
        if not agent_name:
            return None

        agents = {
            "structuring": "planner.agents.structuring_agent.structuring_agent",
            "constraints": "planner.agents.constraints_agent.constraints_agent",
            "prd":         "planner.agents.prd_agent.prd_agent",
            "trd":         "planner.agents.trd_agent.trd_agent",
            "schema":      "planner.agents.schema_agent.schema_agent",
            "design":      "planner.agents.design_agent.design_agent",
            "appflow":     "planner.agents.appflow_agent.appflow_agent",
            "rules":       "planner.agents.rules_agent.rules_agent",
            "implementation": "planner.agents.implementation_agent.implementation_agent",
            "tracker":     "planner.agents.tracker_agent.tracker_agent",
            "modules":     "planner.agents.module_planner_agent.module_planner_agent",
        }

        if agent_name not in agents:
            return None

        import importlib
        dotted = agents[agent_name]
        module_path, fn_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, fn_name)

    def _generate_clarifying_questions(self, structured_idea: str, change_description: str) -> List[str]:
        from planner.tools import get_llm_client
        llm = get_llm_client()
        system = """You are an expert product analyst. The user has requested a change that is ambiguous, unclear, or too vague.
Generate exactly 1 to 3 direct, high-quality clarifying questions to ask the user to specify their change.
Return the questions as a bulleted list, starting with '- '."""
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"StructuredIdea.md content:\n{structured_idea}\n\nChange description:\n{change_description}")
        ]
        response = invoke_llm_safe(messages)
        questions = []
        for line in response.splitlines():
            line = line.strip()
            if line.startswith("- "):
                questions.append(line[2:].strip())
            elif line.startswith("* "):
                questions.append(line[2:].strip())
        if not questions:
            questions = ["Can you please explain the change in more detail?"]
        return questions

    def _generate_impact_context(self, filename: str, summary: ChangeSummary, current_content: str) -> str:
        from planner.tools import get_llm_client
        llm = get_llm_client()
        system = f"You are a technical analyst. Given a change summary and the current content of {filename}, write a single sentence describing exactly what needs to be changed in this file. Be specific."
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"Change Summary:\n- Type: {summary.change_type}\n- What Changed: {summary.what_changed}\n\nCurrent content:\n{current_content}")
        ]
        return invoke_llm_safe(messages).strip()

    def _generate_semantic_diff(self, filename: str, before: str, after: str) -> str:
        from planner.tools import get_llm_client
        llm = get_llm_client()
        system = f"You are a technical editor. Compare the content of {filename} before and after an update. Produce a clean, concise bulleted list summarizing the key semantic changes (what was added, removed, or modified). Do NOT output a raw code/git diff. Be concise and human-friendly."
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"Before Content:\n{before}\n\nAfter Content:\n{after}")
        ]
        return invoke_llm_safe(messages).strip()
