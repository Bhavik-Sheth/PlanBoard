# PlanBoard (PlannerX)

AI-assisted "vibe coding" skips planning — no PRD, no schema, and no decision trail. Manual documentation (like Notion or Google Docs) drifts out of sync fast, while single-shot AI generation lacks a persistent structure or approval process. PlanBoard solves this by bringing automated, structured planning to your terminal, bridging the gap between raw ideas and code.

## What PlanBoard Is
PlanBoard is a terminal-native, multi-agent planning tool designed to construct a complete, structured project specification before a single line of code is written. 

* **Input:** A raw idea, or a structured Problem Statement + proposed solution.
* **Output:** A comprehensive project spec, including a Product Requirement Document (PRD), Technical Requirement Document (TRD), Schema, Rules, Design Decisions, App Flow, and live ASCII architecture diagrams.
* **Core Design:** Instead of relying on a single LLM to generate everything in one shot, PlanBoard orchestrates specialized agents that each own exactly one document. They ask clarifying questions when needed and require your explicit approval before moving on to the next file, ensuring every document is accurate, consistent, and traceable to a decision.

### Getting Started

To install PlanBoard globally:

```bash
# Via pipx (recommended)
pipx install git+https://github.com/Bhavik-Sheth/PlanBoard.git

# Via uv tool
uv tool install git+https://github.com/Bhavik-Sheth/PlanBoard.git
```

To launch PlanBoard, navigate to any project folder and run:

```bash
planboard
```

For detailed guides, provider configurations, and a complete command reference, see the [User Manual](UserManual.md).

## Agents + Workflow
PlanBoard coordinates **16 agents total** using a hub-and-spoke multi-agent architecture.

### Agent Roles
* **Orchestrator:** A pure router that manages execution flow, with no direct user-facing input/output.
* **Executive Agent:** The primary interface and the only agent you talk to directly.
* **Specialist Agents:** Each agent owns and drafts exactly one markdown specification file:
  * **PRD Agent** (Product Requirement Document)
  * **TRD Agent** (Technical Requirement Document)
  * **Schema Agent** (Database and data schemas)
  * **Design Decisions Agent** (Decisions, tradeoffs, and rationale)
  * **App Flow Agent** (User journeys and screen navigation)
  * **Rules Agent** (Code quality and architecture guidelines)
  * **Implementation Plan Agent** (Step-by-step development roadmap)
  * **Modules Agent** (Codebase directory structure and file maps)
* **Support Agents:**
  * **Griller:** Interrogates your assumptions, asking clarifying questions one at a time.
  * **Tech Stack Expert:** Recommends tools, frameworks, and stacks with detailed tradeoff analyses when you are undecided.
  * **Consistency Agent:** Verifies that all drafted documents agree with one another.
  * **Finalizer Agent:** Compiles all approved specifications into a single, execution-ready `CLAUDE.md` context.
  * **Updates Agent:** Propagates adjustments only to affected files rather than triggering a full documentation rebuild.
* **Background Watcher:** A daemon process that regenerates ASCII architecture diagrams live in the background as planning files change.

### Step-by-Step Workflow
1. **Launch:** Run `planboard` in your target project directory.
2. **Describe:** Input your raw idea or a Problem Statement + proposed solution to the Executive Agent.
3. **Draft:** Specialist agents draft each file in sequence.
4. **Approve / Iterate:** Review the drafts, requesting changes or approving each file before proceeding.
5. **Verify:** Run `/consistency` to check cross-file agreement.
6. **Compile:** Run `/finalize` to compile the final `CLAUDE.md` execution context.

## Features
* **Slash-Command Driven UX:** Use a Claude Code-style interactive command interface typed directly into the chat input.
* **Keyboard-First TUI:** A terminal user interface optimized for speed and keyboard navigation; mouse interactions are optional and never required.
* **Provider-Agnostic LLM Layer:** Choose your preferred model provider, including Gemini, Groq, Anthropic, OpenAI, NVIDIA NIM, or any custom OpenAI-compatible API endpoint.
* **ASCII Architecture Diagrams:** Automatic visual rendering of layouts and system networks (powered by PHART and NetworkX) directly in the terminal without requiring external image viewers.
* **Blast-Radius Updates:** Modifying a requirement mid-session recalculates dependencies and only runs updates on affected files, minimizing LLM token consumption.

## Tech Stack
* **Language:** Python
* **Agentic Framework:** LangGraph, LangChain
* **TUI & CLI:** Textual, Typer
* **Layouts & Visuals:** PHART, NetworkX

## Known Issues
* **TUI Lag/Freeze:** You may experience occasional interface lag or freezes during long agent runs.
  * **Workaround:** Press `Ctrl+C` to terminate the process and relaunch PlanBoard. Session state is continuously preserved on disk, so you will not lose any planning progress.

## Contributing
PlanBoard is early and actively evolving. We welcome feedback, issue reports, and pull requests! Feel free to open a PR or start a discussion.
