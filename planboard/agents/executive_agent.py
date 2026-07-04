"""
executive_agent.py — Sole user-facing I/O agent.

The ExecutiveAgent is the ONLY agent that communicates with the user.  It:
  - Receives all raw user input (slash commands, plain text, approvals)
  - Parses and validates input before passing it to the Orchestrator
  - Renders all output from the Orchestrator (Viewer panel, chat, approvals)
  - Manages the startup flow (mode selection, resume prompt)
  - Never makes routing decisions
  - Never calls specialist agents directly
  - Never makes LLM calls — it is purely an I/O bridge

Think of it as the *frontend* to the Orchestrator's backend.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from planboard.state import PlannerState, ExecutiveState, save_state, load_state
from planboard.agents.orchestrator import OrchestratorAgent


# ── Display payload type constants ─────────────────────────────────────────

# All known payload types that the Orchestrator can return
_PAYLOAD_TYPES = {
    "ready", "prompt", "ready_to_run", "file_complete", "file_approved",
    "question", "suggestion", "error", "status_table", "fit_analysis",
    "consistency_report", "finalized", "finalize_warning", "chat_response",
    "confirmation_required", "sequence_complete", "update_complete",
    "module_list",
}

# ── Slash command registry ────────────────────────────────────────────────

_SLASH_COMMANDS = {
    "/init",  "/describe", "/run", "/approve", "/status", "/edit",
    "/reset", "/module", "/update", "/consistency", "/finalize",
    "/diagram", "/help", "/abort", "/config", "/done",
}


class ExecutiveAgent:
    """
    Sole user-facing agent.  Parses input → sends structured commands to
    Orchestrator → renders display payloads back to the user.
    """

    def __init__(self, state: PlannerState) -> None:
        self.state = state
        self.orchestrator = OrchestratorAgent(state)
        self.exec_state: ExecutiveState = {
            "waiting_for": "",
            "pending_command": {},
            "last_display": "",
        }
        # Conversational history for chat_orchestrator context window
        self.chat_history: list[dict] = []

    # ── Input Parsing ──────────────────────────────────────────────────

    def parse_input(self, raw: str) -> dict:
        """
        Classify and package raw user input into a structured command
        for the Orchestrator.

        Returns a dict with at minimum a ``command`` key.
        Returns ``None``-valued command for validation errors that the
        Executive handles directly (returns rendered output instead).
        """
        raw = raw.strip()
        if not raw:
            return {"command": None}

        # ── Slash commands ─────────────────────────────────────────
        if raw.startswith("/"):
            parts = raw.split(maxsplit=1)
            name = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if name == "/init":
                return {"command": "init"}

            elif name == "/describe":
                if not arg:
                    return {"command": None, "_error": "Usage: /describe <your idea text>"}
                return {"command": "describe", "text": arg}

            elif name == "/run":
                return {"command": "run"}

            elif name == "/approve":
                if not arg:
                    return {"command": None, "_error": "Which file? e.g. /approve PRD.md"}
                return {"command": "approve", "file": arg}

            elif name == "/status":
                return {"command": "status"}

            elif name == "/edit":
                if not arg:
                    return {"command": None, "_error": "Which file? e.g. /edit PRD.md"}
                return {"command": "edit", "file": arg}

            elif name == "/reset":
                if not arg:
                    return {"command": None, "_error": "Which file? e.g. /reset PRD.md"}
                return {"command": "reset", "file": arg}

            elif name == "/module":
                sub_parts = arg.split(maxsplit=1)
                sub_cmd = sub_parts[0].lower() if sub_parts else ""
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub_cmd == "add":
                    if not sub_arg:
                        return {"command": None, "_error": "Usage: /module add <name>"}
                    return {"command": "module_add", "name": sub_arg}
                elif sub_cmd == "list" or not sub_cmd:
                    return {"command": "module_list"}
                else:
                    return {"command": None, "_error": f"Unknown module subcommand: {sub_cmd}"}

            elif name == "/update":
                if not arg:
                    return {"command": None, "_error": "Usage: /update <description of changes>"}
                return {"command": "update", "text": arg}

            elif name == "/consistency":
                return {"command": "consistency"}

            elif name == "/finalize":
                return {"command": "finalize"}

            elif name == "/diagram":
                return {"command": "diagram"}

            elif name == "/help":
                return {"command": None, "_help": True}

            elif name == "/abort":
                return {"command": None, "_abort": True}

            elif name == "/done":
                return {"command": None, "_done": True}

            elif name == "/config":
                return {"command": None, "_config": arg}

            else:
                return {"command": None, "_error": f"Unknown command: {name}. Type /help for available commands."}

        # ── Plain text ─────────────────────────────────────────────
        # Route through chat_orchestrator for intent classification
        # so the user can speak naturally and still trigger real pipeline actions.
        return {"command": "_chat_classify", "text": raw}

    # ── Output Rendering ───────────────────────────────────────────────

    def render_payload(self, payload: dict) -> str:
        """
        Take a typed display payload from the Orchestrator and render it
        as a formatted string for the user.
        """
        ptype = payload.get("type", "")

        if ptype == "ready":
            return f"✅ {payload.get('message', 'Ready.')}"

        elif ptype == "prompt":
            return payload.get("text", "")

        elif ptype == "ready_to_run":
            return (
                "✅ StructuredIdea.md generated.\n"
                "Type /run to start the planning pipeline."
            )

        elif ptype == "file_complete":
            file = payload.get("file", "?")
            agent = payload.get("agent", "?")
            summary = payload.get("summary", [])
            lines = [f"✅ {file} written by {agent}.", "", "Key decisions:"]
            for bullet in summary:
                lines.append(f"  • {bullet}")
            lines.append("")
            lines.append(f"Type /approve {file} to accept, or describe changes to revise it.")
            return "\n".join(lines)

        elif ptype == "file_approved":
            file = payload.get("file", "?")
            next_file = payload.get("next_file")
            if next_file:
                return f"✅ {file} approved. Moving to {next_file}..."
            return f"✅ {file} approved. All files complete!"

        elif ptype == "question":
            source = payload.get("source_agent", "Agent")
            text = payload.get("text", "?")
            reason = payload.get("reason", "")
            lines = [
                f"❓ [{source} needs info]",
                f"   {text}",
            ]
            if reason:
                lines.append(f"   (Reason: {reason})")
            lines.append("")
            lines.append('Type your answer, or type "I don\'t know" to get a suggestion.')
            self.exec_state["waiting_for"] = "question_answer"
            return "\n".join(lines)

        elif ptype == "suggestion":
            tool = payload.get("tool", "?")
            why = payload.get("why", "")
            tradeoff = payload.get("tradeoff", "")
            alt = payload.get("alternative", "")
            lines = [
                f"💡 Suggestion: {tool}",
                f"   Why: {why}",
                f"   Trade-off: {tradeoff}",
            ]
            if alt:
                lines.append(f"   Alternative if rejected: {alt}")
            lines.append("")
            lines.append("Accept this suggestion? [yes / no]")
            self.exec_state["waiting_for"] = "suggestion_confirm"
            return "\n".join(lines)

        elif ptype == "error":
            agent = payload.get("agent", "?")
            message = payload.get("message", "Unknown error")
            lines = [
                f"⚠️  Error in {agent}: {message}",
                "",
                "Retry this agent? [yes / no]",
            ]
            self.exec_state["waiting_for"] = "retry_confirm"
            return "\n".join(lines)

        elif ptype == "status_table":
            raw = payload.get("raw", "")
            if raw:
                return raw
            rows = payload.get("rows", [])
            lines = ["| File | Status | Agent | Notes |",
                      "|------|--------|-------|-------|"]
            for r in rows:
                lines.append(
                    f"| {r.get('file', '')} | {r.get('status', '')} "
                    f"| {r.get('agent', '')} | {r.get('notes', '')} |"
                )
            return "\n".join(lines)

        elif ptype == "fit_analysis":
            content = payload.get("content", "")
            has_gaps = payload.get("has_gaps", False)
            lines = [
                "=" * 60,
                "FIT ANALYSIS",
                "=" * 60,
                content,
                "=" * 60,
            ]
            if has_gaps:
                lines.append("")
                lines.append(
                    "Gaps or risks identified above may affect planning.\n"
                    "Proceed with current scope? Or revise your solution first? "
                    "[proceed / revise]"
                )
                self.exec_state["waiting_for"] = "fit_analysis_confirm"
            return "\n".join(lines)

        elif ptype == "consistency_report":
            issues = payload.get("issues", [])
            clean = payload.get("clean", True)
            if clean:
                return "✅ No contradictions detected."
            lines = ["## Consistency Issues Found\n"]
            for issue in issues:
                lines.append(
                    f"- **{issue.get('file_a', '?')}** ↔ "
                    f"**{issue.get('file_b', '?')}**: "
                    f"{issue.get('issue', '?')}"
                )
            lines.append("")
            lines.append(
                "No auto-fix applied. Use /reset <file> to re-run a specific agent."
            )
            return "\n".join(lines)

        elif ptype == "finalized":
            warnings = payload.get("warnings", [])
            lines = []
            if warnings:
                for w in warnings:
                    lines.append(f"⚠️  {w}")
                lines.append("")
            lines.append("✅ CLAUDE.md generated inside PLANBOARD/ alongside PRD.md and TRD.md.")
            lines.append("Planning phase complete. You can now begin implementation.")
            return "\n".join(lines)

        elif ptype == "finalize_warning":
            incomplete = payload.get("incomplete", [])
            lines = ["⚠️  Some files are not yet complete:"]
            for f in incomplete:
                lines.append(f"  - {f}")
            lines.append("")
            lines.append("Proceed with finalization anyway? [yes / no]")
            self.exec_state["waiting_for"] = "finalize_confirm"
            return "\n".join(lines)

        elif ptype == "chat_response":
            return payload.get("text", "")

        elif ptype == "confirmation_required":
            warning = payload.get("warning", "")
            # Use the payload's _waiting_for hint if provided, else default to reset_confirm
            waiting_key = payload.get("_waiting_for", "reset_confirm")
            self.exec_state["waiting_for"] = waiting_key
            self.exec_state["pending_command"] = payload
            return warning

        elif ptype == "sequence_complete":
            return (
                "✅ All planning files are complete!\n"
                "Run /finalize to generate CLAUDE.md."
            )

        elif ptype == "update_complete":
            files_changed = payload.get("files_changed", [])
            stale_warning = payload.get("stale_warning", "")
            lines = []
            if files_changed:
                lines.append(f"✅ Update applied. Files changed: {', '.join(files_changed)}")
            else:
                lines.append("✅ Update completed.")
            if stale_warning:
                lines.append(f"\n⚠️  {stale_warning}")
            return "\n".join(lines)

        elif ptype == "module_list":
            modules = payload.get("modules", [])
            if not modules:
                return "No modules defined yet. Use /module add <name>."
            lines = ["Modules:"]
            for m in modules:
                lines.append(f"  {m.get('status', '⬜')}  {m.get('name', '?')}")
            return "\n".join(lines)

        # Fallback
        return str(payload)

    # ── Help text ──────────────────────────────────────────────────────

    @staticmethod
    def render_help() -> str:
        """Return the help text for all available commands."""
        return "\n".join([
            "Available Commands:",
            "  /init                    - Initialize PLANBOARD/ directory structure",
            "  /describe <text>         - Append raw idea and structure it",
            "  /run                     - Run the planning pipeline to generate drafts",
            "  /status                  - Show planning tracker/status",
            "  /approve <file>          - Approve a planning document",
            "  /reset <file>            - Clear and regenerate a planning document",
            "  /module add <name>       - Add a new code module spec",
            "  /module list             - List existing module specs",
            "  /consistency             - Run documentation consistency audit",
            "  /update <description>    - Request a mid-session plan/requirement change",
            "  /config                  - Configure LLM provider, model, and API keys",
            "  /finalize                - Compile CLAUDE.md and exit planning",
            "  /help                    - Show this help message",
            "  /abort                   - Abort a pending confirmation or question prompt",
            "",
            "To request changes, type your change request directly as plain text.",
        ])

    # ── Main processing entry point ────────────────────────────────────

    def process(
        self,
        raw_input: str,
        active_file: str = "",
    ) -> tuple[Optional[dict], str]:
        """
        Main entry point.  Takes raw user input, returns:
          (command_sent_to_orchestrator, rendered_output_for_user)

        active_file: the file currently open in the viewer (forwarded to
                     chat_orchestrator for context-aware intent classification).
        """
        # Check if we're waiting for a specific response
        if self.exec_state["waiting_for"]:
            return self._handle_waiting_response(raw_input)

        # Parse input
        parsed = self.parse_input(raw_input)

        # Handle local actions
        if parsed.get("command") is None:
            if parsed.get("_help"):
                return None, self.render_help()
            if parsed.get("_error"):
                return None, parsed["_error"]
            if parsed.get("_abort"):
                if self.state.active_update_plan:
                    abort_cmd = {"command": "abort_update"}
                    payload = self.orchestrator.dispatch(abort_cmd)
                    return abort_cmd, self.render_payload(payload)
                self.exec_state["waiting_for"] = ""
                self.exec_state["pending_command"] = {}
                return None, "No active prompt to abort."
            if parsed.get("_done"):
                return None, ""
            if "_config" in parsed:
                return None, self._handle_config_action(parsed["_config"])
            return None, ""

        if parsed.get("command") == "edit":
            from planboard.tools import open_in_editor
            from planboard.utils import resolve_relative_path
            filename = parsed["file"]
            resolved = resolve_relative_path(self.state.project_path, filename)
            if resolved:
                filename = resolved
            filepath = Path(self.state.project_path) / filename
            if not filepath.exists():
                return None, f"⚠️  File not found: {filename}"
            open_in_editor(str(filepath))
            # After edit completes, notify orchestrator
            complete_cmd = {"command": "edit_complete", "file": filename}
            payload = self.orchestrator.dispatch(complete_cmd)
            return complete_cmd, self.render_payload(payload)

        if parsed.get("command") == "diagram":
            from planboard.agents.architecture_diagram_agent import generate_diagrams
            try:
                generate_diagrams(str(self.state.project_path))
                return parsed, "✅ Architecture diagrams regenerated."
            except Exception as e:
                return parsed, f"⚠️  Diagram generation failed: {e}"

        # ── Chat intent classification ──────────────────────────────
        # When the user sends plain text, classify their intent via LLM
        # and translate it into the appropriate orchestrator command.
        if parsed.get("command") == "_chat_classify":
            parsed, rendered = self._handle_chat_classify(
                parsed["text"], active_file
            )
            self.exec_state["last_display"] = rendered
            return parsed, rendered

        # Route to Orchestrator
        payload = self.orchestrator.dispatch(parsed)
        
        # Auto-advance sequence if a file was approved and there is a next file
        if payload.get("type") == "file_approved" and payload.get("next_file"):
            run_payload = self.orchestrator.dispatch({"command": "run"})
            approval_msg = self.render_payload(payload)
            run_msg = self.render_payload(run_payload)
            rendered = f"{approval_msg}\n\n{run_msg}"
            payload = run_payload
        else:
            rendered = self.render_payload(payload)
            
        self.exec_state["last_display"] = rendered

        # Keep chat history updated for slash commands too
        self.chat_history.append({"role": "user", "content": raw_input})
        self.chat_history.append({"role": "assistant", "content": rendered})
        # Keep history bounded to last 20 turns
        if len(self.chat_history) > 40:
            self.chat_history = self.chat_history[-40:]

        return parsed, rendered

    def _handle_chat_classify(
        self, text: str, active_file: str
    ) -> tuple[Optional[dict], str]:
        """
        Classify plain-text user input using chat_orchestrator, then dispatch
        the appropriate real pipeline command. Returns (cmd, rendered_output).
        """
        from planboard.agents.chat_orchestrator import chat_orchestrator
        from planboard.tools import list_planboard_files

        # Gather workspace context for the classifier
        existing_files = list(
            list_planboard_files(str(Path(self.state.project_path).parent)).keys()
        )

        try:
            action = chat_orchestrator(
                user_message=text,
                chat_history=self.chat_history,
                existing_files=existing_files,
                active_file=active_file,
            )
        except Exception as exc:
            # If LLM classification fails, fall back to a plain chat response
            fallback_cmd = {"command": "chat", "text": text}
            payload = self.orchestrator.dispatch(fallback_cmd)
            rendered = self.render_payload(payload)
            self._update_history(text, rendered)
            return fallback_cmd, rendered

        # Always show the LLM's friendly description of what it's doing first
        prefix = action.response_message.strip() if action.response_message else ""

        # Map ChatAction.action → orchestrator command
        cmd: Optional[dict] = None
        action_rendered = ""

        if action.action == "chat":
            # Pure conversational reply — no pipeline action needed
            action_rendered = prefix
            cmd = None

        elif action.action == "init":
            cmd = {"command": "init"}

        elif action.action == "describe":
            if not action.text_content:
                action_rendered = prefix + "\n\n> ⚠️ Could not extract idea text. Please use `/describe <your idea>` directly."
                cmd = None
            else:
                cmd = {"command": "describe", "text": action.text_content}

        elif action.action == "run":
            cmd = {"command": "run"}

        elif action.action == "status":
            cmd = {"command": "status"}

        elif action.action == "approve":
            target = action.target_file or self.state.active_revision_target
            if not target:
                action_rendered = prefix + "\n\n> ⚠️ Could not determine which file to approve. Use `/approve <file>` directly."
                cmd = None
            else:
                cmd = {"command": "approve", "file": target}

        elif action.action == "reset":
            target = action.target_file
            if not target:
                action_rendered = prefix + "\n\n> ⚠️ Could not determine which file to reset. Use `/reset <file>` directly."
                cmd = None
            else:
                cmd = {"command": "reset", "file": target}

        elif action.action == "module_add":
            name = action.module_name
            if not name:
                action_rendered = prefix + "\n\n> ⚠️ Could not determine module name. Use `/module add <name>` directly."
                cmd = None
            else:
                cmd = {"command": "module_add", "name": name}

        elif action.action == "module_list":
            cmd = {"command": "module_list"}

        elif action.action == "consistency":
            cmd = {"command": "consistency"}

        elif action.action == "finalize":
            cmd = {"command": "finalize"}

        elif action.action == "change_request":
            target = action.target_file or self.state.active_revision_target
            change_text = action.text_content or text
            if not target:
                action_rendered = prefix + "\n\n> ⚠️ Could not determine which file to update. Use `/update <description>` or mention the file name."
                cmd = None
            else:
                cmd = {"command": "revise", "target": target, "request": change_text}

        else:
            # Unknown action — fall back to chat
            cmd = {"command": "chat", "text": text}

        # If we have a real command to dispatch, do it
        if cmd is not None:
            payload = self.orchestrator.dispatch(cmd)
            
            # Auto-advance sequence if a file was approved and there is a next file
            if payload.get("type") == "file_approved" and payload.get("next_file"):
                run_payload = self.orchestrator.dispatch({"command": "run"})
                pipeline_rendered = f"{self.render_payload(payload)}\n\n{self.render_payload(run_payload)}"
                payload = run_payload
            else:
                pipeline_rendered = self.render_payload(payload)
                
            if prefix:
                rendered = f"{prefix}\n\n{pipeline_rendered}"
            else:
                rendered = pipeline_rendered
        else:
            rendered = action_rendered

        self._update_history(text, rendered)
        return cmd, rendered

    def _update_history(self, user_msg: str, assistant_msg: str) -> None:
        """Append a turn to chat_history, keeping it bounded to 20 turns."""
        self.chat_history.append({"role": "user", "content": user_msg})
        self.chat_history.append({"role": "assistant", "content": assistant_msg})
        if len(self.chat_history) > 40:
            self.chat_history = self.chat_history[-40:]

    def _handle_config_action(self, arg: str) -> str:
        from planboard.tools import (
            get_active_provider,
            get_active_model,
            set_active_provider,
            set_active_model,
            set_api_key,
            get_api_key_status,
            list_providers,
            PROVIDER_REGISTRY
        )
        import importlib
        
        arg = arg.strip()
        if not arg:
            provider = get_active_provider()
            model = get_active_model()
            keys_status = get_api_key_status()
            
            lines = [
                "Current LLM Configuration:",
                f"  Active Provider: {provider or 'None'}",
                f"  Active Model:    {model or 'None'}",
                "",
                "API Keys Status:"
            ]
            for p, is_set in keys_status.items():
                status_icon = "set" if is_set else "missing"
                lines.append(f"  {p:<12}: {status_icon}")
            
            lines.extend([
                "",
                "Usage:",
                "  /config provider <name>   - Set the active LLM provider",
                "  /config model <name>      - Set the active LLM model",
                "  /config apikey <provider> <key> - Set the API key for a provider"
            ])
            return "\n".join(lines)

        parts = arg.split(maxsplit=2)
        subcmd = parts[0].lower()
        subarg1 = parts[1].strip() if len(parts) > 1 else ""
        subarg2 = parts[2].strip() if len(parts) > 2 else ""

        providers = list_providers()

        if subcmd == "provider":
            if not subarg1:
                return f"Usage: /config provider <{'|'.join(providers)}>"
            if subarg1 not in providers:
                return f"Unknown provider '{subarg1}'. Must be one of: {', '.join(providers)}"

            entry = PROVIDER_REGISTRY[subarg1]
            try:
                importlib.import_module(entry["import_path"])
            except ImportError:
                package_name = entry["import_path"].replace('_', '-')
                return (
                    f"⚠️ Warning: Provider '{subarg1}' requires the '{entry['import_path']}' package.\n"
                    f"Run: uv add {package_name} in your terminal to install it."
                )

            set_active_provider(subarg1)
            return f"✅ Active provider set to: {subarg1}"

        elif subcmd == "model":
            if not subarg1:
                return "Usage: /config model <model_name>"
            model_name = subarg1
            if subarg2:
                model_name = f"{subarg1} {subarg2}"
            set_active_model(model_name)
            return f"✅ Active model set to: {model_name}"

        elif subcmd in ("apikey", "key"):
            if not subarg1 or not subarg2:
                return "Usage: /config apikey <provider> <key_value>"
            if subarg1 not in providers:
                return f"Unknown provider '{subarg1}'. Must be one of: {', '.join(providers)}"
            try:
                set_api_key(subarg1, subarg2)
                return f"✅ API key for provider '{subarg1}' successfully saved to .env"
            except Exception as e:
                return f"Error saving API key: {e}"
        else:
            return f"Unknown config subcommand: {subcmd}. Use provider, model, or apikey."

    def _handle_waiting_response(self, raw: str) -> tuple[Optional[dict], str]:
        """Handle user response when we're waiting for confirmation/answer."""
        waiting = self.exec_state["waiting_for"]
        raw_lower = raw.strip().lower()

        # Allow /abort or /cancel to break out of any waiting state
        if raw_lower in ("/abort", "/cancel"):
            self.exec_state["waiting_for"] = ""
            self.exec_state["pending_command"] = {}
            return None, "Aborted."

        # Allow /help or /config to run immediately
        if raw_lower == "/help":
            return None, self.render_help()
        if raw_lower.startswith("/config"):
            parts = raw.split(maxsplit=1)
            config_arg = parts[1].strip() if len(parts) > 1 else ""
            return None, self._handle_config_action(config_arg)

        # Check if user is trying to send an unrelated command
        if raw.startswith("/"):
            return None, "Please respond to the current prompt first, or type /cancel to abort."

        if waiting == "reset_confirm":
            self.exec_state["waiting_for"] = ""
            pending = self.exec_state.get("pending_command", {})
            if raw_lower in ("yes", "y"):
                # Extract file from pending action (e.g. "reset PRD.md")
                action = pending.get("action", "")
                file = action.replace("reset ", "").strip() if action else ""
                cmd = {"command": "reset_confirmed", "file": file}
                payload = self.orchestrator.dispatch(cmd)
                rendered = self.render_payload(payload)
                self.exec_state["pending_command"] = {}
                return cmd, rendered
            else:
                self.exec_state["pending_command"] = {}
                return None, "Reset cancelled."

        elif waiting == "finalize_confirm":
            self.exec_state["waiting_for"] = ""
            if raw_lower in ("yes", "y"):
                cmd = {"command": "finalize_confirmed"}
                payload = self.orchestrator.dispatch(cmd)
                return cmd, self.render_payload(payload)
            return None, "Finalize cancelled."

        elif waiting == "fit_analysis_confirm":
            self.exec_state["waiting_for"] = ""
            if raw_lower in ("revise", "r"):
                return None, (
                    "Describe your revised solution:\n"
                    "Type /done when finished."
                )
            return None, "Proceeding with current scope. Type /run to continue."

        elif waiting == "question_answer":
            if raw.strip() == "?":
                question = self.state.pending_questions[0] if self.state.pending_questions else ""
                cmd = {"command": "get_suggestion", "question": question}
                payload = self.orchestrator.dispatch(cmd)
                return cmd, self.render_payload(payload)

            self.exec_state["waiting_for"] = ""
            # Store answer in state and continue
            if self.state.pending_questions:
                question = self.state.pending_questions[0]
                self.state.grill_answers[question] = raw
                self.state.pending_questions = self.state.pending_questions[1:]
            save_state(self.state)
            return None, "Answer recorded. Continuing..."

        elif waiting == "suggestion_confirm":
            self.exec_state["waiting_for"] = ""
            accepted = raw_lower in ("yes", "y", "approve", "accept")
            cmd = {"command": "suggestion_response", "accepted": accepted}
            payload = self.orchestrator.dispatch(cmd)
            return cmd, self.render_payload(payload)

        elif waiting == "retry_confirm":
            self.exec_state["waiting_for"] = ""
            if raw_lower in ("yes", "y"):
                # Re-run the last command
                cmd = {"command": "run"}
                payload = self.orchestrator.dispatch(cmd)
                return cmd, self.render_payload(payload)
            return None, "Agent skipped. Use /status to see current state."

        elif waiting == "resume_confirm":
            self.exec_state["waiting_for"] = ""
            confirmed = raw_lower in ("yes", "y")
            cmd = {"command": "resume", "confirmed": confirmed}
            payload = self.orchestrator.dispatch(cmd)
            return cmd, self.render_payload(payload)

        elif waiting == "mode_select":
            self.exec_state["waiting_for"] = ""
            if raw in ("1",):
                cmd = {"command": "set_mode", "mode": "from_scratch"}
            elif raw in ("2",):
                cmd = {"command": "set_mode", "mode": "ps_idea_hybrid"}
            else:
                return None, "Invalid choice. Please enter 1 or 2."
            payload = self.orchestrator.dispatch(cmd)
            return cmd, self.render_payload(payload)

        elif waiting == "update_confirm":
            self.exec_state["waiting_for"] = ""
            if raw_lower in ("yes", "y"):
                cmd = {"command": "update_confirmed"}
                payload = self.orchestrator.dispatch(cmd)
                return cmd, self.render_payload(payload)
            else:
                # Cancel: clear the stored plan
                self.orchestrator.state.active_update_plan = None
                save_state(self.orchestrator.state)
                return None, "Update cancelled."

        # Fallback — clear waiting state
        self.exec_state["waiting_for"] = ""
        return None, ""

    # ── Startup Flow ───────────────────────────────────────────────────

    def handle_startup(self) -> str:
        """
        Handle the startup flow:
          - If PLANBOARD/ exists with StructuredIdea.md → resume prompt
          - Otherwise → mode selection prompt
        """
        planboard_dir = Path(self.state.project_path)
        si_path = planboard_dir / "StructuredIdea.md"

        if si_path.exists() and si_path.stat().st_size > 0:
            # Resume flow — get status from Orchestrator
            payload = self.orchestrator.dispatch({"command": "get_status"})
            status_text = self.render_payload(payload)

            self.exec_state["waiting_for"] = "resume_confirm"
            return (
                "Welcome back to PlanBoard.\n\n"
                "Resuming session. Last status:\n"
                f"{status_text}\n\n"
                "Continue from where we left off? [yes / no]"
            )
        else:
            # Fresh start — mode selection
            self.exec_state["waiting_for"] = "mode_select"
            return (
                "Welcome to PlanBoard.\n\n"
                "How would you like to start?\n\n"
                "  [1] From scratch — I have a raw idea, help me plan it fully\n"
                "  [2] PS + Idea — I have a problem statement and a proposed solution\n\n"
                "Type 1 or 2 to begin."
            )
