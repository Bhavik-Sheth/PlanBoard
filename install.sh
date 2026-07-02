#!/bin/bash
# ============================================================
#  PlanBoard — Global Installation Script
#  Installs PlanBoard as a global CLI tool from GitHub.
#
#  Usage (from anywhere):
#    curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/PlanBoard/main/install.sh | bash
#
#  Or from the local source directory:
#    bash install.sh
#
#  After install, run `planboard` from any project directory.
#  PlanBoard will automatically create PLANBOARD/ in the current folder.
# ============================================================

set -e

REPO_URL="https://github.com/Bhavik-Sheth/PlanBoard"
PACKAGE_SPEC="git+${REPO_URL}.git"

# If running from inside the repo (local install), use the local source
if [ -f "./pyproject.toml" ] && grep -q "name = \"planboard\"" ./pyproject.toml 2>/dev/null; then
    PACKAGE_SPEC="."
    echo "📁 Local source detected — installing from current directory."
else
    echo "🌐 Installing PlanBoard from GitHub: ${REPO_URL}"
fi

echo "=================================================="
echo "         PlanBoard Global Installation            "
echo "=================================================="
echo ""

# ── Method 1: pipx (recommended — isolated environment, global command) ──
if command -v pipx &>/dev/null; then
    echo "✅ pipx detected — using pipx for global isolated install."
    echo "📦 Installing PlanBoard..."
    pipx install "${PACKAGE_SPEC}" --force
    echo ""
    echo "=================================================="
    echo "🎉 PlanBoard installed successfully!"
    echo ""
    echo "Usage:"
    echo "  cd /your/project"
    echo "  planboard"
    echo ""
    echo "PlanBoard will auto-create PLANBOARD/ on first run."
    echo "=================================================="
    exit 0
fi

# ── Method 2: uv tool (alternative — also gives global command) ──
if command -v uv &>/dev/null; then
    echo "✅ uv detected — using 'uv tool' for global install."
    echo "📦 Installing PlanBoard..."
    uv tool install "${PACKAGE_SPEC}" --force
    echo ""
    echo "=================================================="
    echo "🎉 PlanBoard installed successfully via uv tool!"
    echo ""
    echo "Usage:"
    echo "  cd /your/project"
    echo "  planboard"
    echo ""
    echo "PlanBoard will auto-create PLANBOARD/ on first run."
    echo "If 'planboard' is not found, run: uv tool update-shell"
    echo "=================================================="
    exit 0
fi

# ── Method 3: Offer to install pipx, then use it ──
echo "⚠️  Neither 'pipx' nor 'uv' found."
echo ""
echo "Recommended: Install pipx for a clean global Python tool install:"
echo ""
echo "  # On Ubuntu/Debian:"
echo "  sudo apt install pipx && pipx ensurepath"
echo ""
echo "  # On macOS:"
echo "  brew install pipx && pipx ensurepath"
echo ""
echo "  # Via pip:"
echo "  pip install --user pipx && python -m pipx ensurepath"
echo ""
read -rp "Install pipx now via pip and continue? [y/N] " choice
if [[ "$choice" =~ ^[Yy]$ ]]; then
    pip install --user pipx
    python -m pipx ensurepath
    export PATH="$HOME/.local/bin:$PATH"
    pipx install "${PACKAGE_SPEC}" --force
    echo ""
    echo "=================================================="
    echo "🎉 PlanBoard installed! Restart your terminal or run:"
    echo "  source ~/.bashrc   (or ~/.zshrc)"
    echo "=================================================="
    exit 0
fi

# ── Method 4: Local venv fallback (development use) ──
echo ""
echo "Falling back to local venv install (development mode only)."
echo "Note: 'planboard' will only be available inside this venv."
echo ""

if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Please install Python 3.12+."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "⚙️  Creating virtual environment..."
    python3 -m venv .venv
fi

echo "⚙️  Activating virtual environment..."
source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q

# Setup .env if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️  Creating .env configuration file..."
    cp .env.example .env
    echo "✅ .env created. Configure your API key in .env or via the TUI /config command."
fi

echo ""
echo "=================================================="
echo "🎉 PlanBoard installed in local venv!"
echo ""
echo "To use it:"
echo "  source .venv/bin/activate"
echo "  cd /your/project"
echo "  planboard"
echo ""
echo "For a true global install, run: pipx install ."
echo "=================================================="
