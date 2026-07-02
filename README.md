# PlanBoard

PlanBoard is an AI-driven terminal project planboard application designed to draft, refine, and structure product requirements (PRD), technical architecture documents (TRD), schemas, app flows, and coding rules in a single terminal interface (TUI).

Inspired by modern conversational tools like Claude Code and Gemini CLI, PlanBoard provides a single conversational orchestrator agent that interprets your natural language messages, answers questions, manages the planning lifecycle, and automatically triggers specialist agents to write or refine documents.

---

## Key Features

1. **Central Agent Chat Interface**: Chat with a single orchestration agent that resolves your intentions (e.g. initializing, running the pipeline, approving, or making changes to docs).
2. **Interactive TUI Wireframe**: A full-screen Terminal UI built with Textual:
   - **FILE VIEW (Blue)**: Shows active `PLANBOARD/` file structure with reactive updates.
   - **ARCHITECTURE PANEL (Green)**: Renders live-refreshing syntax-highlighted Mermaid diagrams.
   - **VIEWER PANEL (White)**: Displays dynamic log streams and formatted markdown documents.
   - **CHAT INPUT (Orange)**: Default focused prompt for natural conversations and slash commands.
3. **Decoupled Architecture Diagram Watcher**: Standalone process that monitors document changes and automatically regenerates mermaid diagrams.
4. **Interactive Grilling & Suggestions**: Specialist agents consult you with clarification questions or suggest optimal technology stacks which you can approve or customize.
5. **Configurable Settings via TUI**: Easily switch LLM providers (Groq, OpenAI, Anthropic, Nvidia), specify models, and save API keys directly from the TUI.

---

## Layout Wireframe

```
┌──────────────┬─────────────────────────────────────────────┐
│              │  ARCHITECTURE PANEL (Green)                 │
│  FILE VIEW   │  - Syntax-highlighted active .mmd diagram   │
│  (Blue)      ├─────────────────────────────────────────────┤
│              │  RESPONSE / VIEWER PANEL (White)            │
│  PLANBOARD/    │  - Agent logs & streaming stdout/stderr     │
│  ├ RawIdea   │  - Markdown rendering of selected files     │
│  ├ PRD.md    │                                             │
│  ├ ...       │                                             │
│  └ MODULES/  ├─────────────────────────────────────────────┤
│              │  CHAT INPUT (Orange) — prompt line          │
└──────────────┴─────────────────────────────────────────────┘
```

---

## Installation (Global Tool)

PlanBoard is designed to be installed **once** as a global tool and called from **any project directory** — like Claude Code or the GitHub CLI.

### Option 1: Install via `pipx` (Recommended)

```bash
# Install pipx if you don't have it
pip install --user pipx && pipx ensurepath

# Install PlanBoard globally from GitHub
pipx install git+https://github.com/Bhavik-Sheth/PlanBoard.git

# Or from a local clone:
git clone https://github.com/Bhavik-Sheth/PlanBoard.git
pipx install ./PlanBoard
```

### Option 2: Install via `uv tool`

```bash
# Install PlanBoard globally from GitHub
uv tool install git+https://github.com/Bhavik-Sheth/PlanBoard.git

# Or from local clone:
uv tool install ./PlanBoard
```

### Option 3: One-liner (runs install.sh)

```bash
curl -fsSL https://raw.githubusercontent.com/Bhavik-Sheth/PlanBoard/main/install.sh | bash
```

---

## Usage

Once installed, use PlanBoard from **any project directory**:

```bash
# Navigate to your project
cd /your/project

# Launch PlanBoard — PLANBOARD/ is auto-created on first run
planboard
```

On first launch in a new directory, PlanBoard automatically creates `PLANBOARD/` and walks you through the planning flow.

---

## Upgrading

After you push changes to GitHub, update your global install with a single command:

```bash
planboard upgrade
```

This auto-detects whether you installed via `pipx` or `uv tool` and runs the appropriate upgrade. No need to reinstall from scratch.

**Manual alternatives** (if `planboard upgrade` doesn't detect your install method):

```bash
# pipx
pipx install git+https://github.com/Bhavik-Sheth/PlanBoard.git --force

# uv tool
uv tool install git+https://github.com/Bhavik-Sheth/PlanBoard.git --force
```

---

## Configuring Your API Key

On first launch, run `/config` in the TUI to set your LLM provider and API key:

```
/config provider groq
/config apikey groq YOUR_GROQ_API_KEY
```

Or set environment variables before launching:

```bash
export GROQ_API_KEY=your_key_here
planboard
```

---

## Conversational Actions

Type plain text (no prefix) in the **CHAT INPUT** to chat with the Orchestrator. The orchestrator automatically understands what you want to do:

- **General Chat / Help**: Ask `"How do you work?"`, `"What can you do?"`, or generic questions.
- **Initialize project**: `"initialize project"` scaffolds the `PLANBOARD/` directory.
- **Describe project idea**: `"let's plan a python web scraper app"` starts the raw idea structuring.
- **Run planning pipeline**: `"generate all drafts"` or `"run pipeline"` invokes the graph to draft PRD/TRD/Schema files.
- **Document change requests**: Select any file in the File View and type your change (e.g. `"change the database to PostgreSQL in TRD.md"` or `"add a section about unit tests to PRD"`). The agent will regenerate the file incorporating your feedback.
- **Audit consistency**: `"run consistency audit"` looks for contradictions between documents.
- **Finalize planning**: `"finalize project"` compiles the `PLANBOARD/CLAUDE.md` context document.

---

## Slash Commands (Direct Shortcuts)

You can also use slash commands in the Chat Input to trigger actions directly:

- `/help` - Show help menu.
- `/init` - Scaffold `PLANBOARD/` directory.
- `/describe <text>` - Appends raw idea and structures it.
- `/run` - Drafts all project files.
- `/status` - Render `Tracker.md` file status.
- `/approve <file>` - Mark a file as approved in `Tracker.md`.
- `/reset <file>` - Reset a document and re-draft it.
- `/module add <name>` - Add a module specification under `PLANBOARD/MODULES/`.
- `/module list` - List module specifications.
- `/consistency` - Run a read-only document consistency check.
- `/finalize` - Compile the finalized `CLAUDE.md`.
- `/config` - Show current active provider, model, and API keys.
- `/config provider <groq|openai|anthropic|nvidia>` - Set active provider.
- `/config model <model_name>` - Set active model.
- `/config apikey <provider> <key>` - Write API key to `.env`.
- `/abort` - Abort active confirmation prompt or interactive query.

---

## Keyboard Controls

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Cycle focus between panels (File Tree → Architecture → Viewer → Chat Input) |
| `↑` / `↓` | Move selection within focused panel (scroll viewer / move in tree) |
| `→` / `Enter` | Expand folder or open file in Viewer Panel |
| `←` | Collapse folder |
| `Esc` | Return focus to Chat Input |
| `Ctrl+C` / `Ctrl+Q` | Quit PlanBoard cleanly |

---

## Development

Run tests:
```bash
uv run pytest
```
All tests run with mocked API calls and execute locally in under 3 seconds.
