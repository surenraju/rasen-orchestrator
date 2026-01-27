# Integration Tests

Comprehensive end-to-end tests for RASEN orchestrator.

## Overview

These tests verify the full workflow:
1. Build standalone binary with PyInstaller
2. Initialize a new task
3. Run the orchestrator
4. Verify generated code and commits

## Test Levels

### Level 1: Binary Build & CLI (Fast, No API)

Tests that don't require Claude API:
- Binary builds successfully
- Binary reports version correctly
- Init command creates expected files
- Status command works
- Error handling for missing init

**Run:**
```bash
# Run just the fast tests (no API required)
uv run pytest tests/integration/test_binary_fibonacci.py -v -k "not full"

# Or explicitly:
uv run pytest tests/integration/test_binary_fibonacci.py::test_binary_exists
uv run pytest tests/integration/test_binary_fibonacci.py::test_init_command
```

**Duration:** ~30 seconds (includes binary build if needed)

### Level 2: Full Integration (Slow, Requires API)

Complete end-to-end test that actually calls Claude Code CLI:
- Generates a real Fibonacci program
- Verifies plan creation
- Checks generated Python code
- Validates git commits

**Requirements:**
- Claude Code CLI installed: `npm install -g @anthropic-ai/claude-code`
- API key configured: `claude setup-token`
- Set environment variable: `RASEN_INTEGRATION_TEST=1`

**Run:**
```bash
# Enable full integration test
export RASEN_INTEGRATION_TEST=1

# Run full test (takes 5-10 minutes)
uv run pytest tests/integration/test_binary_fibonacci.py::test_run_fibonacci_full -v -s

# Output shows real-time orchestrator progress
```

**Duration:** 5-10 minutes
**Cost:** ~$0.10-0.50 per run (Claude API usage)

## Running All Tests

```bash
# Fast tests only (default)
uv run pytest tests/integration/ -v

# Include full integration tests
RASEN_INTEGRATION_TEST=1 uv run pytest tests/integration/ -v -s

# Run specific test
uv run pytest tests/integration/test_binary_fibonacci.py::test_init_command -v
```

## Test Structure

```python
test_binary_fibonacci.py
├── binary_path fixture        # Builds binary once per module
├── test_project fixture        # Creates temp project with git
├── test_binary_exists()        # ✓ Binary built
├── test_binary_version()       # ✓ Version command works
├── test_binary_help()          # ✓ Help command works
├── test_init_command()         # ✓ Init creates files
├── test_status_before_run()    # ✓ Status after init
├── test_run_fibonacci_full()   # 🔑 FULL TEST (requires API)
├── test_run_without_init_fails() # ✓ Error handling
└── test_init_twice_overwrites()  # ✓ Reinit behavior
```

## What Gets Tested

### Binary Build
- ✅ Binary compiles successfully
- ✅ Binary size is reasonable (>1MB)
- ✅ All dependencies included

### CLI Commands
- ✅ `--version` shows version
- ✅ `--help` shows usage
- ✅ `init --task "..."` creates .rasen directory
- ✅ `init` saves task description to task.txt
- ✅ `init` creates status.json
- ✅ `status` shows current state
- ✅ `run` without init shows clear error

### Full Orchestration (if API enabled)
- ✅ Initializer agent creates implementation_plan.json
- ✅ Coder agent implements subtasks
- ✅ Python files created with Fibonacci implementation
- ✅ Git commits created
- ✅ Final status shows completion

## Expected Outputs

### After `init`
```
fibonacci-test/
├── .rasen/
│   ├── task.txt              # "create fibonacci program in python"
│   └── status.json           # {"status": "initialized", ...}
├── rasen                     # Binary
├── rasen.yml                 # Config
└── README.md                 # Initial commit
```

### After `run` (full test)
```
fibonacci-test/
├── .rasen/
│   ├── task.txt
│   ├── status.json           # {"status": "completed", ...}
│   ├── implementation_plan.json  # Plan with subtasks
│   ├── memories.md           # Cross-session memory
│   ├── attempt_history.json  # Recovery tracking
│   └── prompt_*.md           # Session prompts
├── fibonacci.py              # Generated program
├── tests/                    # Maybe generated tests
├── rasen                     # Binary
├── rasen.yml
└── README.md
```

## Troubleshooting

### Binary build fails

```bash
# Check PyInstaller is installed
uv pip list | grep pyinstaller

# Install if missing
uv pip install pyinstaller

# Try manual build
uv run python build.py
```

### Full test times out

The default timeout is 10 minutes. If your task is complex:

```python
# Edit test_run_fibonacci_full timeout parameter
timeout=1200,  # 20 minutes
```

### API key not found

```bash
# Check Claude Code CLI is configured
claude --version

# Setup token if needed
claude setup-token
```

### Test creates files outside tmp_path

All tests use pytest's `tmp_path` fixture, which creates isolated temp directories that are automatically cleaned up. If you see files in your working directory, it's a bug - please report.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on:
  push:
    branches: [main]
  workflow_dispatch:  # Manual trigger only

jobs:
  integration-fast:
    name: Fast Integration Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest tests/integration/ -v -k "not full"

  integration-full:
    name: Full Integration Test (with API)
    runs-on: ubuntu-latest
    # Only run on manual trigger or main branch
    if: github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install uv
      - run: uv sync
      - run: npm install -g @anthropic-ai/claude-code
      - run: echo "${{ secrets.ANTHROPIC_API_KEY }}" | claude setup-token
      - run: |
          export RASEN_INTEGRATION_TEST=1
          uv run pytest tests/integration/test_binary_fibonacci.py::test_run_fibonacci_full -v -s
```

### Cost Management

Full integration tests cost ~$0.10-0.50 per run. To manage costs:

- Run fast tests on every commit
- Run full tests only on:
  - Manual trigger
  - Release branches
  - Scheduled nightly builds
- Use test markers to skip expensive tests

## Development Workflow

### Adding New Integration Tests

1. Create test function in `test_binary_fibonacci.py`
2. Use `test_project` fixture for isolated environment
3. Add `@pytest.mark.skipif(...)` if requires API
4. Document expected duration and cost
5. Add to CI/CD with appropriate triggers

### Test Guidelines

- **Fast tests (<1 min)**: No API calls, test CLI/binary only
- **Slow tests (>1 min)**: Mark with `@pytest.mark.skipif` and require env var
- **Always use fixtures**: Don't hardcode paths or create global state
- **Clean assertions**: Use descriptive messages
- **Print progress**: Use `-s` flag to see real-time output

## Debugging

### Run test with full output

```bash
uv run pytest tests/integration/test_binary_fibonacci.py::test_run_fibonacci_full -v -s --tb=long
```

### Keep test directory for inspection

```python
# Add to test:
import pytest
@pytest.mark.usefixtures("test_project")
def test_debug(test_project: Path):
    print(f"\nTest project: {test_project}")
    import time; time.sleep(3600)  # Keep alive 1 hour
```

### Check binary includes all dependencies

```bash
dist/rasen --help  # Should work standalone
ldd dist/rasen     # Check dynamic libraries (Linux)
otool -L dist/rasen  # Check dependencies (macOS)
```

## Future Tests

Planned integration tests:
- [ ] Test with review loop enabled
- [ ] Test with QA loop enabled
- [ ] Test background mode (daemon)
- [ ] Test auto-resume after interruption
- [ ] Test with worktrees enabled
- [ ] Multi-subtask complex project
- [ ] Recovery from failures
- [ ] Stall detection triggers
- [ ] Memory persistence across sessions
