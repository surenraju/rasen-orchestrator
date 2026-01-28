.PHONY: help fmt lint typecheck test test-unit test-integration coverage build check all clean install

# Default target
help:
	@echo "RASEN (螺旋) - Development Commands"
	@echo ""
	@echo "Formatting & Linting:"
	@echo "  make fmt          - Format code with ruff"
	@echo "  make lint         - Lint code with ruff (auto-fix)"
	@echo "  make lint-check   - Lint code (check only, no fixes)"
	@echo ""
	@echo "Type Checking:"
	@echo "  make typecheck    - Run mypy type checker"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests (unit + integration)"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make coverage     - Run tests with coverage report"
	@echo "  make coverage-html - Generate HTML coverage report"
	@echo ""
	@echo "Building:"
	@echo "  make build        - Build standalone binary"
	@echo ""
	@echo "Quality Gates:"
	@echo "  make check        - Run all checks (fmt + lint + typecheck + test + coverage)"
	@echo "  make pre-commit   - Run pre-commit orchestration checks"
	@echo ""
	@echo "Utilities:"
	@echo "  make all          - Format, lint, typecheck, test, coverage, build"
	@echo "  make clean        - Remove build artifacts and cache"
	@echo "  make install      - Install dependencies with uv"

# Format code (auto-fix)
fmt:
	@echo "🎨 Formatting code..."
	uv run ruff format .
	@echo "✅ Format complete"

# Lint code (auto-fix)
lint:
	@echo "🔍 Linting code (auto-fix)..."
	uv run ruff check . --fix
	@echo "✅ Lint complete"

# Lint code (check only, no fixes)
lint-check:
	@echo "🔍 Linting code (check only)..."
	uv run ruff check .
	@echo "✅ Lint check passed"

# Type checking
typecheck:
	@echo "📝 Type checking..."
	uv run mypy src/
	@echo "✅ Type check passed"

# Run all tests
test:
	@echo "🧪 Running all tests..."
	uv run pytest
	@echo "✅ All tests passed"

# Run unit tests only
test-unit:
	@echo "🧪 Running unit tests..."
	uv run pytest tests/ --ignore=tests/integration/ -v
	@echo "✅ Unit tests passed"

# Run integration tests only
test-integration:
	@echo "🧪 Running integration tests..."
	uv run pytest tests/integration/ -v --timeout=300
	@echo "✅ Integration tests passed"

# Run tests with coverage
coverage:
	@echo "📊 Running tests with coverage..."
	uv run pytest --cov=rasen --cov-report=term-missing --cov-fail-under=70
	@echo "✅ Coverage check passed"

# Generate HTML coverage report
coverage-html:
	@echo "📊 Generating HTML coverage report..."
	uv run pytest --cov=rasen --cov-report=html
	@echo "✅ Coverage report generated: htmlcov/index.html"
	@echo "   Open with: open htmlcov/index.html"

# Build standalone binary
build:
	@echo "🔨 Building standalone binary..."
	python build.py
	@echo "✅ Binary built: dist/rasen"

# Run all quality checks (MANDATORY before commit)
check: fmt lint-check typecheck test coverage
	@echo ""
	@echo "✅ ✅ ✅  ALL CHECKS PASSED ✅ ✅ ✅"
	@echo ""

# Run pre-commit orchestration checks (for critical files)
pre-commit:
	@echo "🔍 Running pre-commit orchestration checks..."
	./scripts/pre-commit-orchestration.sh

# Full workflow: format, lint, typecheck, test, coverage, build
all: fmt lint typecheck test coverage build
	@echo ""
	@echo "🎉 All tasks completed successfully!"
	@echo ""

# Clean build artifacts and cache
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	uv sync
	@echo "✅ Dependencies installed"
