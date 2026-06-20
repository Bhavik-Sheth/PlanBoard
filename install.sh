#!/bin/bash
set -e

echo "=================================================="
echo "          PlannerX Installation Script           "
echo "=================================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "⚠️ 'uv' is not installed."
    echo "Please install uv first (e.g., via 'curl -LsSf https://astral.sh/uv/install.sh | sh')"
    exit 1
fi

echo "📦 Synchronizing virtual environment and dependencies..."
uv sync

# Setup .env if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️ Creating .env configuration file..."
    cp .env.example .env
    echo "✅ .env created. Please configure your API key in .env or via the TUI."
else
    echo "ℹ️ .env file already exists, skipping."
fi

echo "=================================================="
echo "🎉 PlannerX setup complete!"
echo "To launch the interactive TUI, run:"
echo "    uv run planner"
echo "=================================================="
