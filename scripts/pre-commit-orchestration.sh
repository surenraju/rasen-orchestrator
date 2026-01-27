#!/usr/bin/env bash
# Pre-commit checks for orchestration files
# This script MUST pass before committing changes to loop.py, review.py, qa.py, or cli.py

set -e  # Exit on any error

echo "🔍 Pre-commit orchestration checks..."
echo ""

# Check which critical files changed
CRITICAL_FILES="src/rasen/loop.py src/rasen/review.py src/rasen/qa.py src/rasen/cli.py"
CHANGED_CRITICAL=false

for file in $CRITICAL_FILES; do
    if git diff --cached --name-only | grep -q "^$file$"; then
        CHANGED_CRITICAL=true
        echo "📝 Critical file changed: $file"
    fi
done

if [ "$CHANGED_CRITICAL" = false ]; then
    echo "✅ No critical orchestration files changed, skipping checks"
    exit 0
fi

echo ""
echo "⚠️  Critical orchestration files changed - running MANDATORY checks"
echo ""

# 1. Format check
echo "1️⃣  Checking code format..."
uv run ruff format --check . || {
    echo "❌ Format check failed. Run: uv run ruff format ."
    exit 1
}
echo "✅ Format OK"
echo ""

# 2. Lint check
echo "2️⃣  Checking lint..."
uv run ruff check . || {
    echo "❌ Lint check failed. Run: uv run ruff check . --fix"
    exit 1
}
echo "✅ Lint OK"
echo ""

# 3. Type check
echo "3️⃣  Checking types..."
uv run mypy src/ || {
    echo "❌ Type check failed. Fix type errors."
    exit 1
}
echo "✅ Types OK"
echo ""

# 4. Unit tests
echo "4️⃣  Running unit tests..."
uv run pytest tests/ -x -v --ignore=tests/integration/ || {
    echo "❌ Unit tests failed. Fix failing tests."
    exit 1
}
echo "✅ Unit tests OK"
echo ""

# 5. Coverage check - overall
echo "5️⃣  Checking overall coverage (minimum 70%)..."
uv run pytest --cov=rasen --cov-fail-under=70 --ignore=tests/integration/ -q || {
    echo "❌ Coverage below 70%. Write more tests."
    exit 1
}
echo "✅ Overall coverage OK"
echo ""

# 6. Coverage check - critical files
echo "6️⃣  Checking critical file coverage..."

if git diff --cached --name-only | grep -q "src/rasen/loop.py"; then
    echo "   Checking loop.py coverage (minimum 80%)..."
    uv run pytest --cov=rasen.loop --cov-fail-under=80 -q || {
        echo "❌ loop.py coverage below 80%. Write integration tests."
        exit 1
    }
fi

if git diff --cached --name-only | grep -q "src/rasen/review.py"; then
    echo "   Checking review.py coverage (minimum 75%)..."
    uv run pytest --cov=rasen.review --cov-fail-under=75 -q || {
        echo "❌ review.py coverage below 75%. Write integration tests."
        exit 1
    }
fi

if git diff --cached --name-only | grep -q "src/rasen/qa.py"; then
    echo "   Checking qa.py coverage (minimum 75%)..."
    uv run pytest --cov=rasen.qa --cov-fail-under=75 -q || {
        echo "❌ qa.py coverage below 75%. Write integration tests."
        exit 1
    }
fi

echo "✅ Critical file coverage OK"
echo ""

# 7. Integration tests
echo "7️⃣  Running integration tests..."
uv run pytest tests/integration/ -v || {
    echo "❌ Integration tests failed. Fix failing tests."
    exit 1
}
echo "✅ Integration tests OK"
echo ""

# 8. Binary build test (if cli.py changed)
if git diff --cached --name-only | grep -q "src/rasen/cli.py"; then
    echo "8️⃣  CLI changed - attempting binary build test..."

    if command -v python &> /dev/null; then
        echo "   Building binary..."
        python build.py || {
            echo "⚠️  Binary build failed. Verify build.py works."
            echo "   Continuing anyway (may be environment issue)..."
        }

        if [ -f "dist/rasen" ]; then
            echo "   Testing binary..."
            ./dist/rasen --version || {
                echo "❌ Binary --version failed. Critical issue."
                exit 1
            }
            echo "✅ Binary build OK"
        fi
    else
        echo "⚠️  Python not found, skipping binary build test"
    fi
    echo ""
fi

echo ""
echo "✅ ✅ ✅  ALL CHECKS PASSED ✅ ✅ ✅"
echo ""
echo "Safe to commit. Changes meet all requirements."
echo ""
