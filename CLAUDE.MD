# 螺旋 RASEN - Claude Code Context

```
╔═══════════════════════════════════════════════════════════╗
║   螺旋  RASEN                                             ║
║   Agent Orchestrator                                      ║
║                                                           ║
║   "The spiral that never stops turning"                   ║
╚═══════════════════════════════════════════════════════════╝
```

## Project Overview

Building **RASEN** (螺旋) - a production-ready orchestrator for long-running autonomous coding tasks using Claude Agent SDK.

**Name Origin:** **RA**ju + **S**ur**EN** = RASEN (螺旋 = Spiral in Japanese)

**Implementation Plan:** `docs/plan.md`

### Agent Workflow

```
Initializer → creates plan (session 1)
     │
     ▼
┌─────────┐     changes_requested     ┌──────────┐
│  Coder  │◄────────────────────────►│ Reviewer │ (read-only)
└────┬────┘         approved          └──────────┘
     │ (per subtask, max 3 loops)
     │
     ▼ (after ALL subtasks complete)
┌─────────┐        rejected           ┌────┐
│  Coder  │◄────────────────────────►│ QA │ (read-only)
└─────────┘        approved           └────┘
     │ (max 50 loops)
     ▼
   Done
```

### Agent Types

| Agent | Purpose | Modifies Code | Events |
|-------|---------|---------------|--------|
| **Initializer** | Session 1: Creates plan | Yes | `init.done` |
| **Coder** | Implements subtasks, fixes issues | Yes | `build.done` |
| **Reviewer** | Code review per subtask | **No** | `review.approved`, `review.changes_requested` |
| **QA** | Validates acceptance criteria | **No** | `qa.approved`, `qa.rejected` |

**Key Design:** Coder fixes both review and QA issues. Reviewer and QA are read-only validators.

---

## CRITICAL PROJECT STANDARDS

These rules apply to ALL work on this project. Violations will cause rejection.

### UNACCEPTABLE ACTIONS

- It is UNACCEPTABLE to declare completion without running tests
- It is UNACCEPTABLE to remove or modify existing tests
- It is UNACCEPTABLE to skip verification steps
- It is UNACCEPTABLE to work on multiple subtasks in one session
- It is UNACCEPTABLE to leave uncommitted work at session end
- It is UNACCEPTABLE to mark a subtask "completed" without evidence
- It is UNACCEPTABLE to commit code that fails lint or format checks
- It is UNACCEPTABLE to ignore type checking errors

### Session End Checklist

Before finishing ANY coding session, verify:
- [ ] `uv run ruff check .` passes (lint - REQUIRED)
- [ ] `uv run ruff format --check .` passes (format - REQUIRED)
- [ ] `uv run mypy src/` passes (type check - REQUIRED)
- [ ] `uv run pytest` passes (tests - REQUIRED)
- [ ] Changes committed with descriptive message
- [ ] Progress file updated with session notes
- [ ] Only ONE subtask worked on this session

---

## Code Quality Commands (MANDATORY)

**Run these commands after EVERY code change. Fix ALL issues before committing.**

```bash
# Format code (auto-fix)
uv run ruff format .

# Lint code (auto-fix what's possible)
uv run ruff check . --fix

# Lint code (check only - must pass)
uv run ruff check .

# Type checking (must pass)
uv run mypy src/

# Run tests (must pass)
uv run pytest

# Full quality check (run before commit)
uv run ruff format . && uv run ruff check . --fix && uv run ruff check . && uv run mypy src/ && uv run pytest
```

**If any command fails:**
1. Fix the issue immediately
2. Do NOT proceed until all checks pass
3. Do NOT commit code that fails any check

---

## Python Code Style

### General Rules

```python
# Python 3.12+ required
# All code must pass: ruff check, ruff format, mypy

# Type hints are MANDATORY on all functions
def process_data(items: list[str], count: int) -> dict[str, int]:
    ...

# Use | for union types (not Union)
def get_value(key: str) -> str | None:
    ...

# Pydantic for all data models
from pydantic import BaseModel

class Subtask(BaseModel):
    id: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    attempts: int = 0

# Async patterns with proper typing
async def run_session(client: ClaudeClient, prompt: str) -> SessionResult:
    async with client:
        result = await client.query(prompt)
    return result

# Dataclasses for simple data containers (when Pydantic is overkill)
from dataclasses import dataclass

@dataclass
class Event:
    topic: str
    payload: str
```

### Import Order (enforced by ruff)

```python
# 1. Standard library
import asyncio
import os
from pathlib import Path

# 2. Third-party
from pydantic import BaseModel
import yaml

# 3. Local
from rasen.config import Config
from rasen.models import Subtask
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions | `snake_case` | `get_next_subtask()` |
| Variables | `snake_case` | `commit_count` |
| Classes | `PascalCase` | `PlanStore` |
| Constants | `SCREAMING_SNAKE` | `MAX_RETRIES` |
| Private | `_leading_underscore` | `_internal_method()` |
| Type aliases | `PascalCase` | `SubtaskList = list[Subtask]` |

### Docstrings (Google style)

```python
def validate_completion(events: list[Event], config: Config) -> bool:
    """Validate that completion event has required evidence.

    Args:
        events: List of events from agent output.
        config: Configuration with backpressure settings.

    Returns:
        True if completion is valid, False otherwise.

    Raises:
        ValidationError: If events are malformed.
    """
```

### Error Handling

```python
# Use specific exceptions
class RasenError(Exception):
    """Base exception for rasen errors."""

class ConfigurationError(RasenError):
    """Invalid configuration."""

class SessionTimeoutError(RasenError):
    """Session exceeded time limit."""

# Raise with context
raise ConfigurationError(f"Invalid model: {model}. Expected one of: {VALID_MODELS}")

# Handle specific exceptions
try:
    result = await run_session(client, prompt)
except SessionTimeoutError:
    logger.warning("Session timed out, will retry")
    return SessionResult(status="timeout", ...)
except RasenError:
    raise  # Re-raise known errors
except Exception as e:
    logger.exception("Unexpected error in session")
    raise RasenError(f"Session failed: {e}") from e
```

---

## Reference Implementations

When implementing features, ALWAYS check these cloned repositories for architecture patterns and working code examples:

### ralph-orchestrator (Rust) - `./ralph-orchestrator/`

**Best for:** Process management, signal handling, event-driven loops, stall detection

| Feature | File | What to Copy |
|---------|------|--------------|
| Main loop | `crates/ralph-core/src/event_loop/mod.rs` | Termination reasons, check_termination() pattern |
| State tracking | `crates/ralph-core/src/event_loop/loop_state.rs` | LoopState struct (iteration, failures, cost) |
| Signal handling | `crates/ralph-cli/src/loop_runner.rs` | SIGINT/SIGTERM/SIGHUP handlers, process group |
| Config | `crates/ralph-core/src/config.rs` | Timeout settings, YAML structure |
| Idle timeout | `crates/ralph-adapters/src/pty_executor.rs` | Activity-based timeout with tokio::select! |
| PID file | `crates/ralph-core/src/loop_lock.rs` | Advisory locking with flock() |
| Backpressure | `crates/ralph-core/src/event_parser.rs` | Parse "tests: pass, lint: pass" evidence |
| Task tracking | `crates/ralph-core/src/task_store.rs` | JSONL task persistence |
| Stall detection | `crates/ralph-core/src/event_loop/mod.rs:1015-1088` | task_block_counts, abandoned_task logic |

### Auto-Claude (Python) - `./Auto-Claude/`

**Best for:** Python patterns, attempt tracking, QA loops, status files

| Feature | File | What to Copy |
|---------|------|--------------|
| Build loop | `apps/backend/agents/coder.py` | Main iteration loop, stuck detection |
| Recovery | `apps/backend/services/recovery.py` | Attempt history, circular fix detection |
| QA loop | `apps/backend/qa/loop.py` | Recurring issue detection, escalation |
| Status file | `apps/backend/ui/status.py` | StatusManager with debounced writes |
| Timeouts | `apps/backend/runners/github/gh_client.py` | asyncio.wait_for + exponential backoff |
| Post-session | `apps/backend/agents/session.py` | post_session_processing() pattern |
| Prompts | `apps/backend/agents/coder.py:970-996` | Strongly-worded instructions |

### Anthropic Best Practices

**Source:** `docs/anthropic-long-running-agents-deep-dive.md`

**Critical patterns to follow:**
- **Extended Two-Agent Pattern:** Initializer + Coder foundation, with Reviewer + QA validation loops
- JSON for structured state (less corruption than Markdown)
- Single subtask per session
- "It is UNACCEPTABLE to..." language in prompts
- 3-second delay between sessions
- Fresh context over compaction
- **Read-only validators:** Reviewer and QA cannot modify files, only Coder can
- **Recurring issue escalation:** 3+ occurrences of same QA issue → human intervention

---

## Implementation Patterns

### Stall Detection (from ralph + Auto-Claude)
```python
# Track per-subtask no-commit sessions
if commits_made == 0:
    no_commit_counts[subtask_id] += 1
if no_commit_counts[subtask_id] >= 3:
    return TerminationReason.STALLED

# Circular fix detection (30% keyword similarity)
if jaccard_similarity(current_approach, recent_approaches) >= 0.3:
    return TerminationReason.LOOP_THRASHING
```

### Session Timeout (from ralph)
```python
async def run_with_timeout(coro, timeout_seconds, idle_timeout):
    last_activity = time.time()

    async def check_idle():
        while True:
            if time.time() - last_activity > idle_timeout:
                raise IdleTimeoutError()
            await asyncio.sleep(10)

    return await asyncio.wait_for(coro, timeout=timeout_seconds)
```

### Status File (from Auto-Claude)
```python
# Write every iteration
status = {
    "pid": os.getpid(),
    "iteration": self.iteration,
    "subtask_id": subtask.id,
    "last_activity": datetime.utcnow().isoformat(),
    "status": "running"
}
atomic_write(status, ".rasen/status.json")
```

### Backpressure Validation (from ralph)
```python
def validate_completion(events: list[Event]) -> bool:
    for event in events:
        if event.topic == "build.done":
            payload = event.payload.lower()
            if "tests: pass" in payload and "lint: pass" in payload:
                return True
    return False
```

### Atomic File Writes
```python
def atomic_write(data: dict, path: Path) -> None:
    """Write atomically to prevent corruption on crash."""
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.rename(path)  # Atomic on POSIX
```

### Review Loop (Coder ↔ Reviewer)
```python
async def run_review_loop(config, subtask, project_dir) -> bool:
    """Run review loop after each subtask completion."""
    for iteration in range(MAX_REVIEW_LOOPS):  # max 3
        # Reviewer is READ-ONLY
        result = await run_reviewer_session(config, subtask, read_only=True)

        if result.approved:
            return True

        # Coder fixes review issues
        await run_coder_fix_session(config, subtask, result.feedback)

    return False  # Escalate to human
```

### QA Loop (Coder ↔ QA)
```python
async def run_qa_loop(config, plan, project_dir) -> bool:
    """Run QA loop after all subtasks complete."""
    history = QAHistory()

    for iteration in range(MAX_QA_ITERATIONS):  # max 50
        # QA is READ-ONLY
        result = await run_qa_session(config, plan, read_only=True)
        history.record(result)

        if result.approved:
            return True

        # Check for recurring issues (3+ occurrences)
        if history.has_recurring_issues():
            await escalate_to_human(result.issues)
            return False

        # Coder fixes QA issues
        await run_coder_fix_session(config, "qa-fix", result.issues)

    return False  # Max iterations reached
```

---

## Bash Commands Allowed

Following Anthropic's security model:
- File inspection: `ls`, `cat`, `head`, `tail`, `wc`, `grep`
- Python: `uv`, `python`, `pip`, `pytest`, `mypy`, `ruff`
- Version control: `git`
- Process: `ps`, `lsof`, `sleep`, `pkill`

---

## Testing

```bash
# Run all tests with coverage
uv run pytest tests/ --cov=rasen --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_stall_detection.py -v

# Run specific test function
uv run pytest tests/test_config.py::test_load_defaults -v

# Integration tests (requires SDK)
uv run pytest tests/integration/ -v --timeout=300

# Run tests in parallel (faster)
uv run pytest -n auto
```

---

## Project Structure

```
rasen-orchestrator/
├── CLAUDE.md                    # This file
├── pyproject.toml               # Project config, dependencies, tool settings
├── uv.lock                      # Lock file (committed)
├── rasen.yml.example            # Example configuration
├── src/rasen/
│   ├── __init__.py
│   ├── cli.py                   # CLI commands
│   ├── config.py                # Configuration
│   ├── models.py                # Pydantic models
│   ├── exceptions.py            # Custom exceptions
│   ├── daemon.py                # Background mode
│   ├── loop.py                  # Main orchestration loop
│   ├── session.py               # Session execution + timeout
│   ├── events.py                # Event parsing
│   ├── git.py                   # Git operations
│   ├── worktree.py              # Worktree management
│   ├── client.py                # SDK client factory
│   ├── processing.py            # Post-session processing
│   ├── validation.py            # Backpressure validation
│   ├── prompts.py               # Prompt template rendering
│   ├── review.py                # Coder ↔ Reviewer loop
│   ├── qa.py                    # Coder ↔ QA loop
│   └── stores/
│       ├── __init__.py
│       ├── plan_store.py        # Subtask tracking
│       ├── recovery_store.py    # Attempt history + stall detection
│       ├── status_store.py      # Progress status file
│       └── memory_store.py      # Cross-session memory
├── prompts/
│   ├── initializer.md           # Session 1 prompt
│   ├── coder.md                 # Sessions 2+ prompt
│   ├── reviewer.md              # Code review prompt (read-only)
│   └── qa.md                    # QA validation prompt (read-only)
└── tests/
    ├── __init__.py
    ├── conftest.py              # Pytest fixtures
    ├── test_config.py
    ├── test_models.py
    ├── test_events.py
    ├── test_stores.py
    ├── test_validation.py
    ├── test_git.py
    ├── test_daemon.py
    ├── test_stall_detection.py
    ├── test_review.py           # Review loop tests
    ├── test_qa.py               # QA loop tests
    └── integration/
        ├── __init__.py
        ├── test_simple_task.py
        ├── test_recovery.py
        ├── test_worktree.py
        ├── test_background_mode.py
        └── test_session_timeout.py
```

## CLI Commands

```bash
# Initialize a new task
rasen init --task "Implement user authentication"

# Run in foreground (full loop: Coder → Reviewer → QA)
rasen run

# Run without code review (faster iteration)
rasen run --skip-review

# Run without QA validation
rasen run --skip-qa

# Run with minimal validation (Coder only)
rasen run --skip-review --skip-qa

# Run in background (for multi-hour tasks)
rasen run --background

# Check status
rasen status

# View logs
rasen logs --follow

# Stop background process
rasen stop

# Resume after interruption
rasen resume

# Merge completed work
rasen merge
```

---

## Runtime Files

All runtime state is stored in `.rasen/` directory:

```
.rasen/
├── rasen.pid                    # PID file (background mode)
├── rasen.log                    # Log file (background mode)
├── status.json                  # Real-time progress status
├── implementation_plan.json     # Subtask tracking
├── attempt_history.json         # Recovery tracking
├── good_commits.json            # Rollback targets
└── QA_ESCALATION.md             # Human intervention needed (created by QA loop)
```
