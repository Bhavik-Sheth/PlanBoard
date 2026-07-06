# PlanBoard User Manual

This manual provides a detailed guide on how to install, configure, and operate PlanBoard (PlannerX).

## 1. Installation

PlanBoard is designed to be installed once as a global tool and called from any project directory, similar to Claude Code or the GitHub CLI.

### Option 1: Install via `pipx` (Recommended)

```bash
# Install pipx if you do not have it
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

### Option 3: Quick Installer

```bash
curl -fsSL https://raw.githubusercontent.com/Bhavik-Sheth/PlanBoard/main/install.sh | bash
```

---

## 2. Configuration & API Keys

On first launch, run `/config` in the terminal chat input to configure your LLM provider and API key:

```
/config provider groq
/config apikey groq YOUR_GROQ_API_KEY
```

Alternatively, you can set environment variables before launching PlanBoard:

```bash
export GROQ_API_KEY=your_key_here
planboard
```

---

## 3. Conversational Actions

Type plain text (no prefix) in the chat input to speak naturally with the Orchestrator. The central orchestrator will automatically understand what you want to do:

- **General Chat / Help**: Ask "How do you work?", "What can you do?", or other generic planning questions.
- **Initialize project**: Type "initialize project" to scaffold the `PLANBOARD/` directory.
- **Describe project idea**: Type "let's plan a python web scraper app" to start structuring your idea.
- **Run planning pipeline**: Type "generate all drafts" or "run pipeline" to run the specialist agents sequence.
- **Document change requests**: Type your change request (e.g. "change the database to PostgreSQL in TRD.md" or "add a section about unit tests to PRD"). The Orchestrator will automatically route this change to the correct agent.
- **Audit consistency**: Type "run consistency audit" to check for contradictions.
- **Finalize planning**: Type "finalize project" to compile the `PLANBOARD/CLAUDE.md` context document.

---

## 4. Slash Commands Reference

You can use the following slash commands in the chat input to trigger actions directly:

- `/help` - Show help menu.
- `/init` - Scaffold the `PLANBOARD/` directory structure.
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

## 5. Keyboard Controls

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Cycle focus between panels (File Tree, Architecture, Viewer, Chat Input) |
| `↑` / `↓` | Move selection within focused panel (scroll viewer or move in tree) |
| `→` / `Enter` | Expand folder or open file in Viewer Panel |
| `←` | Collapse folder |
| `Esc` | Return focus to Chat Input |
| `Ctrl+C` / `Ctrl+Q` | Quit PlanBoard cleanly |

---

## 6. Upgrading PlanBoard

Update your global install with a single command after updates are pushed to GitHub:

```bash
planboard upgrade
```

If the automatic upgrade command fails to detect your installation method, run one of these manual reinstall commands:

```bash
# pipx reinstall
pipx install git+https://github.com/Bhavik-Sheth/PlanBoard.git --force

# uv tool reinstall
uv tool install git+https://github.com/Bhavik-Sheth/PlanBoard.git --force
```
