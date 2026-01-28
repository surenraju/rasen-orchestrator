#!/bin/bash
# Development environment setup for RASEN orchestrator

set -e  # Exit on error

echo "🔧 Setting up RASEN development environment..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python 3.12+ required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "✅ uv installed"

# Install dependencies
echo "📦 Installing dependencies..."
uv sync --all-extras

echo "✅ Dependencies installed"

# Create .rasen directory if it doesn't exist
mkdir -p .rasen

echo "✅ Created .rasen directory"

# Run quality checks to ensure environment is working
echo "🔍 Running quality checks..."

echo "  - Formatting check..."
uv run ruff format --check . || {
    echo "⚠️  Format issues found. Run: uv run ruff format ."
}

echo "  - Lint check..."
uv run ruff check . || {
    echo "⚠️  Lint issues found. Run: uv run ruff check . --fix"
}

echo "  - Type check..."
uv run mypy src/ || {
    echo "⚠️  Type errors found. Fix before committing."
}

echo "  - Tests..."
uv run pytest || {
    echo "⚠️  Some tests failing. Review before proceeding."
}

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review state: .rasen/state.json"
echo "  2. Run orchestrator: rasen run"
echo "  3. Check status: rasen status"
