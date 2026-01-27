# 螺旋 RASEN - Implementation Plan

```
╔═══════════════════════════════════════════════════════════╗
║   螺旋  RASEN                                             ║
║   Agent Orchestrator                                      ║
║                                                           ║
║   "The spiral that never stops turning"                   ║
╚═══════════════════════════════════════════════════════════╝
```

**Project:** RASEN (螺旋) - Agent Orchestrator
**Date:** 2026-01-27
**Target:** Production-ready orchestrator for daily coding tasks
**Based On:** Claude Code CLI (execution engine) + Auto-Claude (workflow patterns) + ralph-orchestrator (loop patterns)
**Name Origin:** **RA**ju + **S**ur**EN** = RASEN (螺旋 = Spiral in Japanese)

> **🔑 KEY ARCHITECTURAL DECISION**
> This orchestrator uses **Claude Code CLI as the execution engine** (via subprocess), NOT the claude-agent-sdk Python library.
> This reduces complexity from ~5000 lines to ~500 lines while keeping all the workflow intelligence.
> All agent sessions (Initializer, Coder, Reviewer, QA) are just different prompts passed to `claude chat --file`.

---

## Executive Summary

Build a **minimal production-ready orchestrator** that:
- **Uses Claude Code CLI as the execution engine** (delegates all coding work to Claude Code)
- Thin Python orchestrator manages workflow loops only (Initializer → Coder → Reviewer → QA)
- Implements post-session Python bookkeeping (state tracking, validation)
- Provides git worktree isolation for safe development
- Enforces quality gates (backpressure) before completion
- Tracks attempts and enables recovery from failures
- Supports cross-session memory for context continuity
- **Extends Anthropic's Two-Agent Pattern** with Review + QA validation loops
- **Supports multi-hour unattended background operation**

**Architecture Philosophy:** Instead of building a complex custom orchestrator with the claude-agent-sdk Python library, RASEN uses Claude Code CLI (via subprocess) for all agent sessions. This dramatically simplifies the codebase (~200 lines vs ~5000 lines) while leveraging Claude Code's built-in session management, tool access, context handling, and error recovery.

### Agent Workflow

```
┌───────────────┐
│  Initializer  │  Session 1: Creates implementation_plan.json
└───────┬───────┘
        │
        ▼
┌───────────────┐     changes_requested     ┌────────────┐
│    Coder      │◄─────────────────────────►│  Reviewer  │ (read-only)
│               │         approved          │            │
└───────┬───────┘                           └────────────┘
        │ (per subtask, max 3 review loops)
        │
        ▼ (after ALL subtasks complete)
┌───────────────┐         rejected          ┌────────────┐
│    Coder      │◄─────────────────────────►│     QA     │ (read-only)
│               │         approved          │            │
└───────────────┘                           └────────────┘
        │ (max 50 QA loops)
        ▼
      Done
```

### Agent Types

| Agent | Purpose | Modifies Code | Events |
|-------|---------|---------------|--------|
| **Initializer** | Session 1: Creates plan, init.sh | Yes | `init.done` |
| **Coder** | Implements subtasks, fixes issues | Yes | `build.done` |
| **Reviewer** | Code review (read-only) | **No** | `review.approved`, `review.changes_requested` |
| **QA** | Validates acceptance criteria (read-only) | **No** | `qa.approved`, `qa.rejected` |

**Key Design:**
- **Coder** is the only agent that modifies code (implements AND fixes)
- **Reviewer** and **QA** are read-only validators that loop back to Coder
- Follows Two-Agent Pattern foundation (Initializer + Coder) with validation loops

### Implementation Approach: Claude Code CLI as Execution Engine

**RASEN uses Claude Code CLI (subprocess) instead of building custom SDK integration:**

```python
# All agent sessions run via subprocess
subprocess.run([
    "claude", "chat",
    "--file", "prompt_coder_subtask1.md"
], cwd=project_dir)
```

**Why This Simplifies Everything:**

| Component | Custom SDK Approach | Claude Code CLI Approach |
|-----------|-------------------|------------------------|
| **Session management** | ~500 lines custom code | 3 lines subprocess call |
| **Tool access** | Custom tool registration | Built-in (Read, Write, Edit, Git, Bash, etc.) |
| **Context handling** | Manual state tracking | Automatic (Claude Code handles it) |
| **Error recovery** | Custom retry logic | Built-in |
| **Authentication** | API key management | OAuth (via `claude setup-token`) |
| **Maintenance** | Update SDK manually | Auto-updates via npm |
| **Total complexity** | ~5000 lines | ~200-300 lines |

**What RASEN Actually Builds:**

1. **Thin orchestration loop** (~200 lines)
   - Iterate through subtasks
   - Call Claude Code CLI for each session
   - Track progress in JSON files

2. **Prompt template rendering** (~50 lines)
   - Load prompt templates
   - Substitute variables
   - Write to temp files

3. **Post-session validation** (~100 lines)
   - Check git commits
   - Validate backpressure (tests pass)
   - Update state files

4. **Review & QA loops** (~100 lines)
   - Run Claude Code in review mode
   - Parse feedback files
   - Loop back to coder if needed

**Total: ~500 lines vs ~5000 lines for custom SDK approach**

---

## Project Acceptance Criteria

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Orchestrator runs multi-session coding tasks to completion | E2E test: 5-subtask feature implemented autonomously |
| 2 | Main branch never touched until explicit merge | Git log shows all work on feature branches |
| 3 | Failed sessions don't corrupt state | Kill mid-session, verify state recoverable |
| 4 | Quality gates block incomplete work | Agent claiming "done" without tests fails validation |
| 5 | Recovery works after failures | Simulate 2 failures, verify 3rd attempt succeeds |
| 6 | Memory persists across sessions | Session N+1 references patterns from session N |
| 7 | Background mode runs unattended for hours | Start with --background, check status after 2+ hours |
| 8 | Session timeouts prevent hung sessions | Session exceeding 30min is killed, loop continues |
| 9 | Progress file enables external monitoring | status.json updated every iteration with timestamps |
| 10 | Stall detection aborts unproductive loops | 3 sessions with no commits on same subtask → abort |
| 11 | **Review loop validates each subtask** | Reviewer agent approves or requests changes (max 3 loops) |
| 12 | **QA loop validates full implementation** | QA agent approves against acceptance criteria (max 50 loops) |
| 13 | **Reviewer/QA are read-only** | Reviewer and QA cannot modify files, only Coder can |
| 14 | **Recurring issues escalate to human** | 3+ occurrences of same QA issue → creates escalation file |

---

## Anthropic Best Practices Alignment

This plan **extends** the **Two-Agent Pattern** from Anthropic's engineering blog with Review + QA validation loops.

### Session Types

```
┌─────────────────────────────────────────────────────────────┐
│                 SESSION 1: INITIALIZER AGENT                │
│  Creates foundation for all future sessions                 │
│  - init.sh script (environment setup)                       │
│  - claude-progress.txt (session notes)                      │
│  - implementation_plan.json (subtask tracking)              │
│  - Initial git commit                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           SESSIONS 2+: CODER → REVIEWER LOOP                │
│  For EACH subtask:                                          │
│  1. Coder implements subtask (commits, runs tests)          │
│  2. Reviewer validates (read-only, emits verdict)           │
│  3. If changes_requested → Coder fixes (max 3 loops)        │
│  4. If approved → move to next subtask                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (after ALL subtasks complete)
┌─────────────────────────────────────────────────────────────┐
│              FINAL VALIDATION: CODER → QA LOOP              │
│  Validates acceptance criteria against full implementation: │
│  1. QA reviews against spec (read-only, emits verdict)      │
│  2. If rejected → Coder fixes (max 50 loops)                │
│  3. If approved → task complete                             │
│  4. Recurring issues (3+) → escalate to human               │
└─────────────────────────────────────────────────────────────┘
```

### Key Patterns from Anthropic

| Pattern | Implementation |
|---------|----------------|
| **Claude Code CLI as execution engine** | All agent sessions run via `claude chat --file prompt.md` |
| **JSON for structured state** | `implementation_plan.json` - subtask status only field agents modify |
| **Progress file** | `claude-progress.txt` - session notes for context across windows |
| **Git as communication** | Commits document intent; history enables rollback |
| **Single feature per session** | Coder works on ONE subtask, commits, updates progress |
| **3-second delay** | `time.sleep(3)` between subprocess calls to Claude Code |
| **Fresh context** | New Claude Code session per iteration (no state carryover) |
| **End-to-end verification** | Backpressure requires "tests: pass" before completion |
| **Strongly-worded instructions** | Prompts include: "It is UNACCEPTABLE to skip tests or declare completion without evidence" |

### Failure Mode Prevention

| Problem | Solution |
|---------|----------|
| Declares victory too early | Dual-confirmation + backpressure validation |
| Leaves buggy progress | Post-session Python processing verifies commits |
| Marks features done prematurely | Require "tests: pass, lint: pass" in build.done event |
| Wastes time on setup | Initializer creates init.sh; coder reads it first |
| Removes or edits tests | Strongly-worded prompt: "NEVER remove or modify existing tests" |

---

## Phase 0: Project Setup

**Goal:** Initialize Python project with modern tooling and best practices

**Prerequisites:**
- Python 3.12+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- OAuth token configured (`claude setup-token`)

### Task 0.1: Python Project Initialization

**Description:** Create Python project `rasen-orchestrator` with uv, ruff, mypy, pytest

**Note:** This project does NOT depend on `anthropic` SDK or `claude-agent-sdk`. All AI interactions happen via Claude Code CLI subprocess calls.

**Deliverables:**
```
rasen-orchestrator/
├── pyproject.toml           # All config in one file
├── uv.lock                  # Dependency lock file
├── src/rasen/
│   └── __init__.py          # Package marker with version
├── tests/
│   ├── __init__.py
│   └── conftest.py          # Pytest fixtures
└── README.md                # Basic readme
```

**pyproject.toml Contents:**
```toml
[project]
name = "rasen-orchestrator"
version = "0.1.0"
description = "Production-ready orchestrator for long-running autonomous coding tasks"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    # No anthropic SDK needed - we use Claude Code CLI via subprocess
    "click>=8.1.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "pytest-xdist>=3.0.0",
    "mypy>=1.13.0",
    "ruff>=0.8.0",
    "types-pyyaml>=6.0.0",
]

[project.scripts]
rasen = "rasen.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/rasen"]

# Ruff configuration
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate (commented out code)
    "PL",     # pylint
    "RUF",    # ruff-specific
]
ignore = [
    "PLR0913",  # Too many arguments
    "PLR2004",  # Magic value comparison
]

[tool.ruff.lint.isort]
known-first-party = ["rasen"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

# Mypy configuration
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_configs = true
show_error_codes = true
files = ["src/rasen"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

# Pytest configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-v --tb=short"

# Coverage configuration
[tool.coverage.run]
source = ["src/rasen"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

**Acceptance Criteria:**
- [ ] `uv sync` installs all dependencies
- [ ] `uv run ruff check .` passes with no errors
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run mypy src/` passes with no errors
- [ ] `uv run pytest` runs (even with no tests yet)
- [ ] `uv run rasen --help` shows usage (after CLI is added)

**Testing:**
- Verify all tool commands work
- Verify import `from rasen import __version__` works

**Verification:**
```bash
cd rasen-orchestrator
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest
```

---

## Phase 1: Foundation

**Goal:** Core infrastructure - config, logging, CLI skeleton

### Task 1.1: Project Structure & Exceptions

**Depends on:** Task 0.1

**Description:** Create file structure and base exception hierarchy

**Deliverables:**
```
src/rasen/
├── __init__.py              # Version, exports
├── exceptions.py            # Exception hierarchy
├── logging.py               # Logging setup
└── py.typed                 # PEP 561 marker
```

**exceptions.py:**
```python
"""RASEN exception hierarchy."""


class RasenError(Exception):
    """Base exception for all RASEN errors."""


class ConfigurationError(RasenError):
    """Invalid or missing configuration."""


class SessionError(RasenError):
    """Error during agent session execution."""


class SessionTimeoutError(SessionError):
    """Session exceeded time limit."""


class IdleTimeoutError(SessionError):
    """Session idle (no output) for too long."""


class ValidationError(RasenError):
    """Validation failed (backpressure, state, etc.)."""


class GitError(RasenError):
    """Git operation failed."""


class StoreError(RasenError):
    """State store operation failed."""


class StallDetectedError(RasenError):
    """Stall condition detected, aborting."""

    def __init__(self, reason: str, termination_reason: "TerminationReason") -> None:
        super().__init__(reason)
        self.termination_reason = termination_reason
```

**Acceptance Criteria:**
- [ ] All source files have proper `__init__.py` exports
- [ ] Exception hierarchy is importable
- [ ] `py.typed` marker present for type checking
- [ ] Logging configured with both console and file handlers

**Testing:**
- Unit: Import all exceptions
- Unit: Logging outputs to both console and file

**Verification:**
```python
from rasen.exceptions import RasenError, ConfigurationError, SessionTimeoutError
from rasen import __version__
assert __version__ == "0.1.0"
```

---

### Task 1.2: Configuration System

**Depends on:** Task 1.1

**Description:** YAML-based configuration with sensible defaults

**Deliverables:**
- `src/rasen/config.py` - Config loader with Pydantic models
- `rasen.yml.example` - Example config

**Config Structure:**
```yaml
# rasen.yml
project:
  name: "my-project"
  root: "."

orchestrator:
  max_iterations: 50
  max_runtime_seconds: 14400        # 4 hours (for multi-hour runs)
  session_delay_seconds: 3
  session_timeout_seconds: 1800     # 30 minutes per session max
  idle_timeout_seconds: 300         # 5 minutes no output = stalled

agent:
  model: "claude-sonnet-4-20250514"
  max_thinking_tokens: 4096

worktree:
  enabled: true
  base_path: ".worktrees"

memory:
  enabled: true
  path: ".rasen/memories.md"
  max_tokens: 2000

backpressure:
  require_tests: true
  require_lint: true

background:
  enabled: false                    # Use --background flag to enable
  pid_file: ".rasen/rasen.pid"
  log_file: ".rasen/rasen.log"
  status_file: ".rasen/status.json"

stall_detection:
  max_no_commit_sessions: 3         # Abort if 3 sessions with no commits
  max_consecutive_failures: 5       # Abort after 5 consecutive failures
  circular_fix_threshold: 0.3       # 30% keyword similarity = circular fix

review:
  enabled: true                     # Run Coder ↔ Reviewer loop per subtask
  max_loops: 3                      # Max review iterations before escalating

qa:
  enabled: true                     # Run Coder ↔ QA loop after all subtasks
  max_iterations: 50                # Max QA iterations
  recurring_issue_threshold: 3      # Escalate after 3+ occurrences of same issue
```

**Implementation:**
```python
"""Configuration loading and validation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Project identification."""
    name: str = "unnamed-project"
    root: Path = Field(default_factory=Path.cwd)


class OrchestratorConfig(BaseModel):
    """Orchestration loop settings."""
    max_iterations: int = 50
    max_runtime_seconds: int = 14400  # 4 hours
    session_delay_seconds: int = 3
    session_timeout_seconds: int = 1800  # 30 min
    idle_timeout_seconds: int = 300  # 5 min


class AgentConfig(BaseModel):
    """Claude agent settings."""
    model: str = "claude-sonnet-4-20250514"
    max_thinking_tokens: int | None = 4096


class WorktreeConfig(BaseModel):
    """Git worktree settings."""
    enabled: bool = True
    base_path: str = ".worktrees"


class MemoryConfig(BaseModel):
    """Cross-session memory settings."""
    enabled: bool = True
    path: str = ".rasen/memories.md"
    max_tokens: int = 2000


class BackpressureConfig(BaseModel):
    """Quality gate settings."""
    require_tests: bool = True
    require_lint: bool = True


class BackgroundConfig(BaseModel):
    """Background daemon settings."""
    enabled: bool = False
    pid_file: str = ".rasen/rasen.pid"
    log_file: str = ".rasen/rasen.log"
    status_file: str = ".rasen/status.json"


class StallDetectionConfig(BaseModel):
    """Stall detection thresholds."""
    max_no_commit_sessions: int = 3
    max_consecutive_failures: int = 5
    circular_fix_threshold: float = 0.3


class ReviewConfig(BaseModel):
    """Review loop settings (Coder ↔ Reviewer)."""
    enabled: bool = True
    max_loops: int = 3


class QAConfig(BaseModel):
    """QA loop settings (Coder ↔ QA)."""
    enabled: bool = True
    max_iterations: int = 50
    recurring_issue_threshold: int = 3


class Config(BaseModel):
    """Root configuration model."""
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    worktree: WorktreeConfig = Field(default_factory=WorktreeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    backpressure: BackpressureConfig = Field(default_factory=BackpressureConfig)
    background: BackgroundConfig = Field(default_factory=BackgroundConfig)
    stall_detection: StallDetectionConfig = Field(default_factory=StallDetectionConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    qa: QAConfig = Field(default_factory=QAConfig)


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from YAML file with environment overrides.

    Priority (highest to lowest):
    1. Environment variables (RASEN_AGENT_MODEL, etc.)
    2. Config file (rasen.yml)
    3. Defaults

    Args:
        config_path: Path to config file. If None, searches for rasen.yml.

    Returns:
        Validated Config object.

    Raises:
        ConfigurationError: If config file is invalid.
    """
    # Find config file
    if config_path is None:
        config_path = Path("rasen.yml")

    # Load from file if exists
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Apply environment overrides
    data = _apply_env_overrides(data)

    # Validate and return
    return Config.model_validate(data)


def _apply_env_overrides(data: dict) -> dict:
    """Apply RASEN_* environment variables as overrides."""
    env_mappings = {
        "RASEN_AGENT_MODEL": ("agent", "model"),
        "RASEN_MAX_ITERATIONS": ("orchestrator", "max_iterations"),
        "RASEN_SESSION_TIMEOUT": ("orchestrator", "session_timeout_seconds"),
    }

    for env_var, (section, key) in env_mappings.items():
        if value := os.environ.get(env_var):
            if section not in data:
                data[section] = {}
            # Convert to int if needed
            if key.endswith(("_seconds", "_iterations", "_tokens")):
                value = int(value)
            data[section][key] = value

    return data
```

**Acceptance Criteria:**
- [ ] Loads from `rasen.yml` if present
- [ ] Falls back to defaults if missing
- [ ] Environment variables override file config (`RASEN_AGENT_MODEL`, etc.)
- [ ] Validates all fields with Pydantic
- [ ] Clear error messages for invalid config

**Testing:**
- Unit: Load config with all fields
- Unit: Load config with missing optional fields
- Unit: Environment override (`RASEN_AGENT_MODEL=claude-opus-4-20250514`)
- Unit: Invalid config raises ConfigurationError

**Verification:**
```python
config = load_config()
assert config.agent.model == "claude-sonnet-4-20250514"
assert config.orchestrator.max_iterations == 50
```

---

### Task 1.3: Data Models

**Depends on:** Task 1.1

**Description:** Pydantic models for all domain objects

**Deliverables:**
- `src/rasen/models.py`

**Implementation:**
```python
"""Domain models for RASEN orchestrator."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TerminationReason(str, Enum):
    """Reasons for loop termination."""
    COMPLETE = "complete"
    MAX_ITERATIONS = "max_iterations"
    MAX_RUNTIME = "max_runtime"
    STALLED = "stalled"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    LOOP_THRASHING = "loop_thrashing"
    USER_CANCELLED = "user_cancelled"
    SESSION_TIMEOUT = "session_timeout"
    ERROR = "error"


class SessionStatus(str, Enum):
    """Status of a completed session."""
    CONTINUE = "continue"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SubtaskStatus(str, Enum):
    """Status of a subtask."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Subtask(BaseModel):
    """A single subtask in the implementation plan."""
    id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING
    attempts: int = 0
    last_approach: str | None = None


class ImplementationPlan(BaseModel):
    """The full implementation plan with subtasks."""
    task_name: str
    subtasks: list[Subtask]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AttemptRecord(BaseModel):
    """Record of a single attempt at a subtask."""
    subtask_id: str
    session: int
    success: bool
    approach: str
    commit_hash: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Event(BaseModel):
    """Event extracted from agent output."""
    topic: str
    payload: str


class SessionResult(BaseModel):
    """Result of a single agent session."""
    status: SessionStatus
    output: str
    commits_made: int
    events: list[Event] = Field(default_factory=list)
    duration_seconds: float = 0.0


class LoopState(BaseModel):
    """Current state of the orchestration loop."""
    iteration: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    current_subtask_id: str | None = None
    completion_confirmations: int = 0
    consecutive_failures: int = 0
    total_commits: int = 0
```

**Acceptance Criteria:**
- [ ] All models have type hints
- [ ] JSON serialization/deserialization works
- [ ] Enums are string-based for JSON compatibility
- [ ] Default values are sensible

**Testing:**
- Unit: Create each model with valid data
- Unit: Validation rejects invalid data
- Unit: JSON round-trip preserves data
- Unit: Enum serialization to string

**Verification:**
```python
from rasen.models import ImplementationPlan, Subtask, SubtaskStatus

plan = ImplementationPlan(
    task_name="auth",
    subtasks=[Subtask(id="auth-1", description="Add login")]
)
json_str = plan.model_dump_json()
restored = ImplementationPlan.model_validate_json(json_str)
assert plan.task_name == restored.task_name
```

---

### Task 1.4: CLI Skeleton

**Depends on:** Task 1.2

**Description:** CLI entry point with basic commands

**Deliverables:**
- `src/rasen/cli.py`

**Implementation:**
```python
"""RASEN CLI - Command line interface."""
from __future__ import annotations

import click

from rasen import __version__
from rasen.config import load_config


@click.group()
@click.version_option(version=__version__, prog_name="rasen")
@click.pass_context
def main(ctx: click.Context) -> None:
    """RASEN - Agent Orchestrator for long-running coding tasks."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()


@main.command()
@click.option("--task", "-t", required=True, help="Task description")
@click.pass_context
def init(ctx: click.Context, task: str) -> None:
    """Initialize a new task."""
    click.echo(f"Initializing task: {task}")
    # Implementation in later task


@main.command()
@click.option("--background", is_flag=True, help="Run in background")
@click.option("--skip-review", is_flag=True, help="Skip Coder ↔ Reviewer loop")
@click.option("--skip-qa", is_flag=True, help="Skip Coder ↔ QA loop")
@click.pass_context
def run(ctx: click.Context, background: bool, skip_review: bool, skip_qa: bool) -> None:
    """Run the orchestration loop."""
    config = ctx.obj["config"]
    # Override config with CLI flags
    if skip_review:
        config.review.enabled = False
    if skip_qa:
        config.qa.enabled = False
    click.echo(f"Running orchestrator (background={background}, review={config.review.enabled}, qa={config.qa.enabled})")
    # Implementation in later task


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current status."""
    click.echo("Status: Not running")
    # Implementation in later task


@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.pass_context
def logs(ctx: click.Context, follow: bool) -> None:
    """View orchestrator logs."""
    click.echo("Logs not available")
    # Implementation in later task


@main.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop background orchestrator."""
    click.echo("Stop command")
    # Implementation in later task


@main.command()
@click.pass_context
def resume(ctx: click.Context) -> None:
    """Resume after interruption."""
    click.echo("Resume command")
    # Implementation in later task


@main.command()
@click.pass_context
def merge(ctx: click.Context) -> None:
    """Merge completed worktree."""
    click.echo("Merge command")
    # Implementation in later task


if __name__ == "__main__":
    main()
```

**Acceptance Criteria:**
- [ ] `rasen --help` shows all commands
- [ ] `rasen --version` shows version
- [ ] Each command is stubbed and callable
- [ ] Config loaded and available in context

**Testing:**
- Unit: CLI argument parsing
- Unit: Each command callable

**Verification:**
```bash
uv run rasen --help
uv run rasen --version
uv run rasen init --task "Test task"
```

---

## Phase 2: Claude Code CLI Integration

**Goal:** Create wrapper for executing agent sessions via Claude Code CLI

### Task 2.1: Claude Code CLI Wrapper

**Depends on:** Task 1.2, Task 1.3

**Description:** Create subprocess wrapper for running Claude Code sessions with different agent prompts

**Deliverables:**
- `src/rasen/claude_runner.py`

**NOTE:** Claude Code CLI is invoked via subprocess:
```bash
# Claude Code CLI uses OAuth token (from `claude setup-token`)
claude chat --file prompt.md
```

**Implementation:**
```python
"""Claude Code CLI wrapper for agent sessions."""
from __future__ import annotations

import subprocess
from pathlib import Path

from rasen.config import Config
from rasen.exceptions import SessionError


# Agent type configurations
AGENT_CONFIGS: dict[str, dict] = {
    "initializer": {
        "prompt_template": "prompts/initializer.md",
        "read_only": False,
    },
    "coder": {
        "prompt_template": "prompts/coder.md",
        "read_only": False,
    },
    "reviewer": {
        "prompt_template": "prompts/reviewer.md",
        "read_only": True,  # Reviewer cannot modify files
    },
    "qa": {
        "prompt_template": "prompts/qa.md",
        "read_only": True,  # QA cannot modify files
    },
}


def run_claude_session(
    prompt_file: Path,
    project_dir: Path,
    timeout_seconds: int = 1800,  # 30 minutes default
) -> subprocess.CompletedProcess:
    """
    Run a Claude Code CLI session.

    Args:
        prompt_file: Path to prompt markdown file
        project_dir: Working directory for the session
        timeout_seconds: Session timeout in seconds

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        SessionError: If Claude Code CLI fails or times out
    """
    try:
        result = subprocess.run(
            ["claude", "chat", "--file", str(prompt_file)],
            cwd=project_dir,
            timeout=timeout_seconds,
            capture_output=False,  # Show output to user in real-time
            check=False,  # Don't raise on non-zero exit
        )
        return result
    except subprocess.TimeoutExpired as e:
        raise SessionError(f"Session timed out after {timeout_seconds}s") from e
    except FileNotFoundError as e:
        raise SessionError(
            "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        ) from e
    except Exception as e:
        raise SessionError(f"Failed to run Claude Code session: {e}") from e


def get_agent_config(agent_type: str) -> dict:
    """Get configuration for an agent type."""
    if agent_type not in AGENT_CONFIGS:
        from rasen.exceptions import ConfigurationError
        raise ConfigurationError(f"Invalid agent type: {agent_type}")
    return AGENT_CONFIGS[agent_type]
```

**Acceptance Criteria:**
- [ ] Runs Claude Code CLI with prompt file
- [ ] Supports session timeout
- [ ] Shows real-time output to user
- [ ] Handles missing CLI gracefully
- [ ] Returns exit code for validation

**Testing:**
- Unit: Verify subprocess call arguments
- Unit: Timeout raises SessionError
- Unit: Missing CLI raises helpful error
- Integration: Run simple session with test prompt

**Verification:**
```python
from rasen.claude_runner import run_claude_session, get_agent_config
from pathlib import Path

prompt_file = Path(".rasen/test_prompt.md")
prompt_file.write_text("Say hello and exit")

result = run_claude_session(prompt_file, Path.cwd(), timeout_seconds=60)
assert result.returncode == 0

agent_cfg = get_agent_config("coder")
assert "prompt_template" in agent_cfg
```

---

### Task 2.2: Prompt Template Renderer

**Depends on:** Task 2.1

**Description:** Render agent prompt templates with variable substitution

**Deliverables:**
- `src/rasen/prompts.py`

**Implementation:**
```python
"""Prompt template rendering for agent sessions."""
from __future__ import annotations

from pathlib import Path

from rasen.exceptions import ConfigurationError


def render_prompt(
    template_path: Path,
    variables: dict[str, str],
) -> str:
    """
    Render prompt template with variable substitution.

    Args:
        template_path: Path to prompt markdown template
        variables: Dictionary of {variable_name: value} for substitution

    Returns:
        Rendered prompt string

    Raises:
        ConfigurationError: If template file doesn't exist
    """
    if not template_path.exists():
        raise ConfigurationError(f"Prompt template not found: {template_path}")

    template = template_path.read_text()

    # Simple {variable} substitution
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        template = template.replace(placeholder, str(value))

    return template


def create_agent_prompt(
    agent_type: str,
    prompts_dir: Path,
    **variables,
) -> str:
    """
    Create a prompt for a specific agent type.

    Args:
        agent_type: Type of agent (initializer, coder, reviewer, qa)
        prompts_dir: Directory containing prompt templates
        **variables: Variables to substitute in template

    Returns:
        Rendered prompt string
    """
    from rasen.claude_runner import get_agent_config

    config = get_agent_config(agent_type)
    template_path = prompts_dir / config["prompt_template"]

    return render_prompt(template_path, variables)
```

**Acceptance Criteria:**
- [ ] Loads prompt template from file
- [ ] Substitutes variables in template
- [ ] Raises clear error for missing template
- [ ] Works with all agent types

**Testing:**
- Unit: Render template with simple variables
- Unit: Missing template raises error
- Unit: All agent types have valid templates

**Verification:**
```python
from rasen.prompts import render_prompt, create_agent_prompt
from pathlib import Path

# Test direct rendering
template = Path("test_template.md")
template.write_text("Hello {name}!")
result = render_prompt(template, {"name": "World"})
assert result == "Hello World!"

# Test agent prompt creation
prompt = create_agent_prompt("coder", Path("prompts"), subtask_id="1", description="Add feature")
assert "subtask" in prompt.lower()
```

---

### Task 2.3: Event Parser

**Depends on:** Task 1.3

**Description:** Extract events from agent output

**Deliverables:**
- `src/rasen/events.py`

**Event Format:**
```xml
<event topic="build.done">tests: pass, lint: pass. Implemented auth.</event>
<event topic="build.blocked">TypeScript errors in auth.ts</event>
<event topic="init.done">Created 5 subtasks. Ready for coding sessions.</event>
```

**Implementation:**
```python
"""Event parsing from agent output."""
from __future__ import annotations

import re

from rasen.models import Event


def parse_events(output: str) -> list[Event]:
    """
    Extract <event> tags from agent output.

    Args:
        output: Raw agent output text.

    Returns:
        List of Event objects extracted from output.
    """
    events: list[Event] = []
    pattern = r'<event\s+topic="([^"]+)">(.*?)</event>'

    for match in re.finditer(pattern, output, re.DOTALL):
        topic = match.group(1).strip()
        payload = match.group(2).strip()
        events.append(Event(topic=topic, payload=payload))

    return events


def has_completion_event(events: list[Event]) -> bool:
    """Check if events contain a completion signal."""
    completion_topics = {"build.done", "init.done"}
    return any(e.topic in completion_topics for e in events)


def has_blocked_event(events: list[Event]) -> bool:
    """Check if events contain a blocked signal."""
    return any(e.topic == "build.blocked" for e in events)


def get_event_payload(events: list[Event], topic: str) -> str | None:
    """Get payload for a specific event topic."""
    for event in events:
        if event.topic == topic:
            return event.payload
    return None
```

**Acceptance Criteria:**
- [ ] Extracts all event tags
- [ ] Handles multiline payloads
- [ ] Ignores malformed tags
- [ ] Returns empty list if no events
- [ ] Strips whitespace from topic and payload

**Testing:**
- Unit: Single event extraction
- Unit: Multiple events extraction
- Unit: Nested content handling
- Unit: No events returns empty list
- Unit: Malformed tags ignored

**Verification:**
```python
output = '<event topic="build.done">tests: pass, lint: pass</event>'
events = parse_events(output)
assert len(events) == 1
assert events[0].topic == "build.done"
assert "tests: pass" in events[0].payload
```

---

## Phase 3: State Management

**Goal:** Reliable state persistence and recovery

### Task 3.1: Plan Store

**Depends on:** Task 1.3

**Description:** Load/save implementation plans

**Deliverables:**
- `src/rasen/stores/plan_store.py`

**File Location:** `.rasen/implementation_plan.json`

**Implementation:**
```python
"""Implementation plan persistence."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rasen.exceptions import StoreError
from rasen.models import ImplementationPlan, Subtask, SubtaskStatus
from rasen.stores._atomic import atomic_write, file_lock


class PlanStore:
    """Manages implementation plan persistence."""

    def __init__(self, rasen_dir: Path) -> None:
        """
        Initialize plan store.

        Args:
            rasen_dir: Path to .rasen directory.
        """
        self.path = rasen_dir / "implementation_plan.json"
        self.rasen_dir = rasen_dir

    def load(self) -> ImplementationPlan | None:
        """
        Load implementation plan from disk.

        Returns:
            ImplementationPlan or None if not exists.

        Raises:
            StoreError: If file exists but is corrupted.
        """
        if not self.path.exists():
            return None

        try:
            with file_lock(self.path, shared=True):
                content = self.path.read_text()
                return ImplementationPlan.model_validate_json(content)
        except Exception as e:
            raise StoreError(f"Failed to load plan: {e}") from e

    def save(self, plan: ImplementationPlan) -> None:
        """
        Save implementation plan atomically.

        Args:
            plan: Plan to save.
        """
        plan.updated_at = datetime.utcnow()
        self.rasen_dir.mkdir(parents=True, exist_ok=True)

        with file_lock(self.path, shared=False):
            atomic_write(self.path, plan.model_dump_json(indent=2))

    def has_plan(self) -> bool:
        """Check if plan exists."""
        return self.path.exists()

    def get_next_subtask(self) -> Subtask | None:
        """
        Get next pending subtask.

        Returns:
            First pending subtask or None if all complete.
        """
        plan = self.load()
        if plan is None:
            return None

        for subtask in plan.subtasks:
            if subtask.status == SubtaskStatus.PENDING:
                return subtask

        return None

    def mark_in_progress(self, subtask_id: str) -> None:
        """Mark subtask as in progress."""
        self._update_subtask_status(subtask_id, SubtaskStatus.IN_PROGRESS)

    def mark_complete(self, subtask_id: str) -> None:
        """Mark subtask as completed."""
        self._update_subtask_status(subtask_id, SubtaskStatus.COMPLETED)

    def mark_failed(self, subtask_id: str) -> None:
        """Mark subtask as failed."""
        self._update_subtask_status(subtask_id, SubtaskStatus.FAILED)

    def increment_attempts(self, subtask_id: str, approach: str) -> None:
        """Increment attempt count and record approach."""
        plan = self.load()
        if plan is None:
            raise StoreError("No plan to update")

        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                subtask.attempts += 1
                subtask.last_approach = approach
                break

        self.save(plan)

    def get_completion_stats(self) -> tuple[int, int]:
        """
        Get completion statistics.

        Returns:
            Tuple of (completed_count, total_count).
        """
        plan = self.load()
        if plan is None:
            return (0, 0)

        completed = sum(
            1 for s in plan.subtasks if s.status == SubtaskStatus.COMPLETED
        )
        return (completed, len(plan.subtasks))

    def _update_subtask_status(self, subtask_id: str, status: SubtaskStatus) -> None:
        """Update subtask status."""
        plan = self.load()
        if plan is None:
            raise StoreError("No plan to update")

        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                subtask.status = status
                break

        self.save(plan)
```

**Acceptance Criteria:**
- [ ] Creates file if not exists
- [ ] Atomic writes (temp file + rename)
- [ ] File locking for concurrent access
- [ ] Validates on load
- [ ] Clear error messages

**Testing:**
- Unit: Save and load round-trip
- Unit: get_next_subtask returns first pending
- Unit: mark_complete updates correct subtask
- Unit: Concurrent access doesn't corrupt

**Verification:**
```python
store = PlanStore(Path(".rasen"))
store.save(plan)
loaded = store.load()
assert loaded.task_name == plan.task_name
```

---

### Task 3.2: Atomic File Operations

**Depends on:** Task 1.1

**Description:** Cross-platform atomic file operations

**Deliverables:**
- `src/rasen/stores/_atomic.py`

**Implementation:**
```python
"""Atomic file operations for safe state persistence."""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Platform-specific locking
if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def file_lock(path: Path, shared: bool = False) -> Iterator[None]:
        """Windows file locking using msvcrt."""
        # Ensure file exists
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        with open(path, "r+b") as f:
            try:
                if shared:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBRLCK, 1)
                else:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                yield
            finally:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
else:
    import fcntl

    @contextmanager
    def file_lock(path: Path, shared: bool = False) -> Iterator[None]:
        """Unix file locking using fcntl."""
        # Ensure file exists
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        with open(path, "r+b") as f:
            try:
                if shared:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                else:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def atomic_write(path: Path, content: str) -> None:
    """
    Write content atomically using temp file + rename.

    This ensures that readers never see partial writes.

    Args:
        path: Target file path.
        content: Content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        temp_path.write_text(content)
        temp_path.replace(path)  # Atomic on POSIX, close-enough on Windows
    except Exception:
        # Clean up temp file on failure
        temp_path.unlink(missing_ok=True)
        raise
```

**Acceptance Criteria:**
- [ ] Works on both Unix and Windows
- [ ] Atomic write never leaves partial files
- [ ] File locking prevents concurrent corruption
- [ ] Temp file cleaned up on failure

**Testing:**
- Unit: Atomic write creates file
- Unit: Atomic write doesn't corrupt on failure
- Unit: File lock is exclusive
- Unit: File lock is reentrant safe

---

### Task 3.3: Recovery Store

**Depends on:** Task 3.2

**Description:** Track attempts and enable recovery

**Deliverables:**
- `src/rasen/stores/recovery_store.py`

**Files:**
- `.rasen/attempt_history.json`
- `.rasen/good_commits.json`

**Implementation:**
```python
"""Recovery and attempt tracking."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from rasen.models import AttemptRecord
from rasen.stores._atomic import atomic_write, file_lock


class AttemptHistory(BaseModel):
    """Persisted attempt history."""
    records: list[AttemptRecord] = []


class GoodCommits(BaseModel):
    """Known-good commits for rollback."""
    commits: list[dict] = []  # {hash, subtask_id, timestamp}


class RecoveryStore:
    """Manages recovery state and attempt tracking."""

    def __init__(self, rasen_dir: Path) -> None:
        self.history_path = rasen_dir / "attempt_history.json"
        self.commits_path = rasen_dir / "good_commits.json"
        self.rasen_dir = rasen_dir

    def record_attempt(
        self,
        subtask_id: str,
        session: int,
        success: bool,
        approach: str,
        commit_hash: str | None = None,
    ) -> None:
        """Record an attempt for recovery context."""
        history = self._load_history()
        history.records.append(
            AttemptRecord(
                subtask_id=subtask_id,
                session=session,
                success=success,
                approach=approach,
                commit_hash=commit_hash,
            )
        )
        self._save_history(history)

    def get_failed_approaches(self, subtask_id: str) -> list[str]:
        """Get approaches that failed for context injection."""
        history = self._load_history()
        return [
            r.approach
            for r in history.records
            if r.subtask_id == subtask_id and not r.success
        ]

    def get_attempt_count(self, subtask_id: str) -> int:
        """Get total attempts for a subtask."""
        history = self._load_history()
        return sum(1 for r in history.records if r.subtask_id == subtask_id)

    def record_good_commit(self, commit_hash: str, subtask_id: str) -> None:
        """Record known-good commit for rollback."""
        commits = self._load_commits()
        commits.commits.append({
            "hash": commit_hash,
            "subtask_id": subtask_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._save_commits(commits)

    def get_last_good_commit(self) -> str | None:
        """Get most recent good commit for rollback."""
        commits = self._load_commits()
        if commits.commits:
            return commits.commits[-1]["hash"]
        return None

    def is_thrashing(self, subtask_id: str, threshold: int = 3) -> bool:
        """Detect if subtask is stuck (N consecutive failures)."""
        history = self._load_history()
        subtask_records = [
            r for r in history.records if r.subtask_id == subtask_id
        ]

        if len(subtask_records) < threshold:
            return False

        # Check last N records
        recent = subtask_records[-threshold:]
        return all(not r.success for r in recent)

    def _load_history(self) -> AttemptHistory:
        if not self.history_path.exists():
            return AttemptHistory()
        with file_lock(self.history_path, shared=True):
            return AttemptHistory.model_validate_json(
                self.history_path.read_text()
            )

    def _save_history(self, history: AttemptHistory) -> None:
        self.rasen_dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.history_path, shared=False):
            atomic_write(self.history_path, history.model_dump_json(indent=2))

    def _load_commits(self) -> GoodCommits:
        if not self.commits_path.exists():
            return GoodCommits()
        with file_lock(self.commits_path, shared=True):
            return GoodCommits.model_validate_json(
                self.commits_path.read_text()
            )

    def _save_commits(self, commits: GoodCommits) -> None:
        self.rasen_dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.commits_path, shared=False):
            atomic_write(self.commits_path, commits.model_dump_json(indent=2))
```

**Acceptance Criteria:**
- [ ] Persists across sessions
- [ ] Tracks per-subtask history
- [ ] Detects thrashing pattern
- [ ] Provides rollback target
- [ ] Thread-safe with file locking

**Testing:**
- Unit: Record and retrieve attempts
- Unit: Thrashing detection after 3 failures
- Unit: Good commit tracking
- Integration: Recovery across process restarts

**Verification:**
```python
store = RecoveryStore(Path(".rasen"))
store.record_attempt("sub-1", 1, False, "JWT approach")
store.record_attempt("sub-1", 2, False, "Session approach")
store.record_attempt("sub-1", 3, False, "Cookie approach")
assert store.is_thrashing("sub-1") == True
assert "JWT approach" in store.get_failed_approaches("sub-1")
```

---

### Task 3.4: Memory Store

**Depends on:** Task 3.2

**Description:** Markdown-based cross-session memory

**Deliverables:**
- `src/rasen/stores/memory_store.py`

**File Location:** `.rasen/memories.md`

**Format:**
```markdown
# Memories

## Patterns
### mem-20260127-001
> Use barrel exports for cleaner imports
<!-- tags: typescript, architecture | created: 2026-01-27T10:30:00Z -->

## Decisions
### mem-20260127-002
> Using Pydantic v2 for all models
<!-- tags: python, models | created: 2026-01-27T11:00:00Z -->
```

**Implementation:**
```python
"""Cross-session memory persistence."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from rasen.stores._atomic import atomic_write, file_lock


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    type: Literal["pattern", "decision", "fix"]
    content: str
    tags: list[str]
    created_at: datetime


class MemoryStore:
    """Manages cross-session memory in Markdown format."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Memory]:
        """Parse memories from markdown file."""
        if not self.path.exists():
            return []

        content = self.path.read_text()
        return self._parse_memories(content)

    def append(self, memory: Memory) -> None:
        """Append new memory to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing content or create template
        if self.path.exists():
            content = self.path.read_text()
        else:
            content = "# Memories\n\n## Patterns\n\n## Decisions\n\n## Fixes\n"

        # Find section and append
        section_map = {
            "pattern": "## Patterns",
            "decision": "## Decisions",
            "fix": "## Fixes",
        }
        section = section_map.get(memory.type, "## Patterns")

        # Format memory entry
        entry = self._format_memory(memory)

        # Insert after section header
        if section in content:
            parts = content.split(section)
            parts[1] = f"\n{entry}" + parts[1]
            content = section.join(parts)
        else:
            content += f"\n{section}\n{entry}"

        with file_lock(self.path, shared=False):
            atomic_write(self.path, content)

    def format_for_injection(self, max_tokens: int = 2000) -> str:
        """Format memories for prompt injection."""
        memories = self.load()
        if not memories:
            return ""

        lines = ["## Relevant Memories from Previous Sessions\n"]
        token_estimate = 10  # Header

        for memory in reversed(memories):  # Most recent first
            entry = f"- **{memory.type}**: {memory.content}\n"
            entry_tokens = len(entry.split()) * 1.3  # Rough estimate

            if token_estimate + entry_tokens > max_tokens:
                break

            lines.append(entry)
            token_estimate += entry_tokens

        return "".join(lines)

    def search(self, query: str) -> list[Memory]:
        """Search memories by content/tags."""
        memories = self.load()
        query_lower = query.lower()

        return [
            m for m in memories
            if query_lower in m.content.lower()
            or any(query_lower in tag.lower() for tag in m.tags)
        ]

    def _parse_memories(self, content: str) -> list[Memory]:
        """Parse markdown content into Memory objects."""
        memories = []
        pattern = r'### (mem-\d{8}-\d+)\n> (.*?)\n<!-- tags: (.*?) \| created: (.*?) -->'

        for match in re.finditer(pattern, content, re.DOTALL):
            mem_id = match.group(1)
            mem_content = match.group(2).strip()
            tags = [t.strip() for t in match.group(3).split(",")]
            created = datetime.fromisoformat(match.group(4))

            # Determine type from section
            start = match.start()
            before = content[:start]
            if "## Decisions" in before and "## Fixes" not in before[before.rfind("## Decisions"):]:
                mem_type = "decision"
            elif "## Fixes" in before:
                mem_type = "fix"
            else:
                mem_type = "pattern"

            memories.append(Memory(
                id=mem_id,
                type=mem_type,
                content=mem_content,
                tags=tags,
                created_at=created,
            ))

        return memories

    def _format_memory(self, memory: Memory) -> str:
        """Format memory as markdown entry."""
        tags_str = ", ".join(memory.tags)
        timestamp = memory.created_at.isoformat()
        return f"### {memory.id}\n> {memory.content}\n<!-- tags: {tags_str} | created: {timestamp} -->\n"

    def create_memory_id(self) -> str:
        """Generate unique memory ID."""
        date = datetime.utcnow().strftime("%Y%m%d")
        # Count existing memories for today
        memories = self.load()
        today_count = sum(1 for m in memories if date in m.id)
        return f"mem-{date}-{today_count + 1:03d}"
```

**Acceptance Criteria:**
- [ ] Human-readable markdown format
- [ ] File-locked for concurrent access
- [ ] Truncates to token budget
- [ ] Searchable by tags/content
- [ ] Unique ID generation

**Testing:**
- Unit: Parse existing memories file
- Unit: Append new memory
- Unit: Token budget truncation
- Unit: Search by tag

**Verification:**
```python
store = MemoryStore(Path(".rasen/memories.md"))
mem_id = store.create_memory_id()
store.append(Memory(
    id=mem_id,
    type="pattern",
    content="Use barrel exports",
    tags=["typescript"],
    created_at=datetime.utcnow(),
))
memories = store.load()
assert any("barrel exports" in m.content for m in memories)
```

---

## Phase 4: Orchestration Loop

**Goal:** Main loop with quality gates and termination

### Task 4.1: Post-Session Processing

**Depends on:** Task 3.1, Task 3.3

**Description:** Python bookkeeping after every session (Critical pattern)

**Deliverables:**
- `src/rasen/processing.py`

**Implementation:**
```python
"""Post-session processing - Python-side bookkeeping."""
from __future__ import annotations

from pathlib import Path

from rasen.events import has_completion_event, get_event_payload
from rasen.git import count_new_commits, get_current_commit
from rasen.models import SessionResult, SessionStatus
from rasen.stores.memory_store import Memory, MemoryStore
from rasen.stores.plan_store import PlanStore
from rasen.stores.recovery_store import RecoveryStore
from rasen.validation import validate_completion


async def post_session_processing(
    rasen_dir: Path,
    project_dir: Path,
    subtask_id: str,
    session_num: int,
    commit_before: str,
    session_result: SessionResult,
    recovery_store: RecoveryStore,
    plan_store: PlanStore,
    memory_store: MemoryStore,
    require_backpressure: bool = True,
) -> bool:
    """
    Process session results in Python (100% reliable).

    This function NEVER trusts the agent's claim of completion.
    It verifies actual work was done.

    Steps:
    1. Count actual commits made
    2. Validate backpressure evidence (if completion claimed)
    3. Record attempt in recovery store
    4. Update plan if complete
    5. Extract and save insights to memory

    Args:
        rasen_dir: Path to .rasen directory.
        project_dir: Path to project root.
        subtask_id: ID of current subtask.
        session_num: Current session number.
        commit_before: Commit hash before session started.
        session_result: Result from session execution.
        recovery_store: Recovery state store.
        plan_store: Plan state store.
        memory_store: Memory store.
        require_backpressure: Whether to require tests/lint evidence.

    Returns:
        True if subtask completed successfully, False otherwise.
    """
    # 1. Count actual commits
    commit_after = get_current_commit(project_dir)
    commits_made = count_new_commits(project_dir, commit_before)
    session_result.commits_made = commits_made

    # 2. Determine if completion is valid
    completion_claimed = has_completion_event(session_result.events)
    success = False

    if completion_claimed:
        if require_backpressure:
            # Validate backpressure evidence
            build_done_payload = get_event_payload(
                session_result.events, "build.done"
            )
            if build_done_payload and validate_completion(build_done_payload):
                success = True
            # init.done doesn't require backpressure
            elif get_event_payload(session_result.events, "init.done"):
                success = True
        else:
            success = True

        # Must have actual commits (except for init which might just create plan)
        if success and commits_made == 0:
            init_done = get_event_payload(session_result.events, "init.done")
            if not init_done:
                success = False

    # 3. Record attempt
    approach = _extract_approach(session_result.output)
    recovery_store.record_attempt(
        subtask_id=subtask_id,
        session=session_num,
        success=success,
        approach=approach,
        commit_hash=commit_after if commits_made > 0 else None,
    )

    # 4. Update plan status
    if success:
        plan_store.mark_complete(subtask_id)
        if commits_made > 0:
            recovery_store.record_good_commit(commit_after, subtask_id)
    else:
        plan_store.increment_attempts(subtask_id, approach)

    # 5. Extract insights to memory (on success)
    if success:
        _extract_memories(session_result.output, memory_store)

    return success


def _extract_approach(output: str) -> str:
    """Extract approach description from session output."""
    # Look for approach description in output
    # This is a heuristic - agent should describe their approach
    lines = output.split("\n")
    for line in lines:
        if "approach" in line.lower() or "trying" in line.lower():
            return line[:200]

    # Fallback: first non-empty line
    for line in lines:
        if line.strip():
            return line[:200]

    return "Unknown approach"


def _extract_memories(output: str, memory_store: MemoryStore) -> None:
    """Extract memorable insights from session output."""
    # Look for explicit memory markers
    # Agent can use: <!-- memory: pattern: description -->
    import re
    from datetime import datetime

    pattern = r'<!-- memory: (\w+): (.*?) -->'
    for match in re.finditer(pattern, output):
        mem_type = match.group(1)
        content = match.group(2)

        if mem_type in ("pattern", "decision", "fix"):
            memory_store.append(Memory(
                id=memory_store.create_memory_id(),
                type=mem_type,
                content=content,
                tags=[],
                created_at=datetime.utcnow(),
            ))
```

**Acceptance Criteria:**
- [ ] Never trusts agent's claim of completion
- [ ] Verifies actual commits made
- [ ] Validates backpressure evidence
- [ ] Updates state atomically
- [ ] Extracts memories from output

**Testing:**
- Unit: Success path - commits made, tests pass
- Unit: Failure path - no commits made
- Unit: Rejection path - commits but tests fail
- Integration: Full session → processing flow

**Verification:**
```python
# Simulate agent claiming done without commits
result = SessionResult(status=SessionStatus.COMPLETE, commits_made=0, ...)
success = await post_session_processing(..., session_result=result)
assert success == False  # Rejected - no actual work done
```

---

### Task 4.2: Backpressure Validator

**Depends on:** Task 2.3

**Description:** Enforce quality gates before completion

**Deliverables:**
- `src/rasen/validation.py`

**Implementation:**
```python
"""Backpressure validation for quality gates."""
from __future__ import annotations

from dataclasses import dataclass

from rasen.config import BackpressureConfig
from rasen.models import Event


@dataclass
class BackpressureEvidence:
    """Evidence of quality checks passing."""
    tests_passed: bool
    lint_passed: bool

    def all_passed(self) -> bool:
        """Check if all required gates passed."""
        return self.tests_passed and self.lint_passed


def validate_backpressure(payload: str) -> BackpressureEvidence:
    """
    Parse backpressure evidence from event payload.

    Looks for: "tests: pass", "lint: pass"
    Case-insensitive matching.

    Args:
        payload: Event payload string.

    Returns:
        BackpressureEvidence with parsed results.
    """
    payload_lower = payload.lower()

    return BackpressureEvidence(
        tests_passed="tests: pass" in payload_lower,
        lint_passed="lint: pass" in payload_lower,
    )


def validate_completion(payload: str, config: BackpressureConfig | None = None) -> bool:
    """
    Validate that completion has required evidence.

    Args:
        payload: Event payload from build.done event.
        config: Backpressure config (uses defaults if None).

    Returns:
        True if completion is valid, False otherwise.
    """
    if config is None:
        config = BackpressureConfig()

    evidence = validate_backpressure(payload)

    if config.require_tests and not evidence.tests_passed:
        return False

    if config.require_lint and not evidence.lint_passed:
        return False

    return True


def format_rejection_message(evidence: BackpressureEvidence) -> str:
    """Format human-readable rejection message."""
    missing = []

    if not evidence.tests_passed:
        missing.append("tests: pass")
    if not evidence.lint_passed:
        missing.append("lint: pass")

    return f"Missing required evidence: {', '.join(missing)}"
```

**Acceptance Criteria:**
- [ ] Rejects completion without evidence
- [ ] Configurable requirements (tests, lint)
- [ ] Case-insensitive matching
- [ ] Clear rejection message

**Testing:**
- Unit: Valid evidence passes
- Unit: Missing tests fails
- Unit: Missing lint fails
- Unit: Case-insensitive matching

**Verification:**
```python
evidence = validate_backpressure("tests: pass, lint: pass")
assert evidence.all_passed() == True

evidence = validate_backpressure("tests: FAIL, lint: pass")
assert evidence.all_passed() == False
```

---

### Task 4.3: Main Orchestration Loop

**Depends on:** Task 4.1, Task 4.2, Task 2.2

**Description:** Core loop coordinating all components

**Deliverables:**
- `src/rasen/loop.py`

**Implementation:**
```python
"""Main orchestration loop."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.models import LoopState, TerminationReason
from rasen.processing import post_session_processing
from rasen.prompts import create_agent_prompt
from rasen.stores.memory_store import MemoryStore
from rasen.stores.plan_store import PlanStore
from rasen.stores.recovery_store import RecoveryStore
from rasen.stores.status_store import StatusStore
from rasen.git import get_current_commit

logger = logging.getLogger(__name__)


class OrchestrationLoop:
    """Main orchestration loop for RASEN."""

    def __init__(
        self,
        config: Config,
        rasen_dir: Path,
        project_dir: Path,
    ) -> None:
        self.config = config
        self.rasen_dir = rasen_dir
        self.project_dir = project_dir

        # Initialize stores
        self.plan_store = PlanStore(rasen_dir)
        self.recovery_store = RecoveryStore(rasen_dir)
        self.memory_store = MemoryStore(
            Path(config.memory.path) if config.memory.enabled else rasen_dir / "memories.md"
        )
        self.status_store = StatusStore(
            Path(config.background.status_file)
        )

        # Loop state
        self.state = LoopState()

    def run(self) -> TerminationReason:
        """
        Main orchestration loop.

        Returns:
            Reason for termination.
        """
        logger.info("Starting orchestration loop")
        self.status_store.mark_started()

        try:
            while True:
                # Check termination conditions
                if reason := self._check_termination():
                    logger.info(f"Terminating: {reason}")
                    self.status_store.mark_terminated(reason.value)
                    return reason

                # Determine session type
                is_initializer = not self.plan_store.has_plan()

                if is_initializer:
                    # Session 1: Initializer
                    success = self._run_initializer_session()
                else:
                    # Sessions 2+: Coder
                    subtask = self.plan_store.get_next_subtask()

                    if subtask is None:
                        # All subtasks complete - dual confirmation
                        self.state.completion_confirmations += 1
                        if self.state.completion_confirmations >= 2:
                            return TerminationReason.COMPLETE
                        logger.info(
                            f"Completion confirmation {self.state.completion_confirmations}/2"
                        )
                        time.sleep(self.config.orchestrator.session_delay_seconds)
                        continue

                    # Reset confirmation counter on new work
                    self.state.completion_confirmations = 0

                    success = self._run_coder_session(subtask)

                # Update state
                self.state.iteration += 1

                # Delay between sessions
                time.sleep(self.config.orchestrator.session_delay_seconds)

        except Exception as e:
            logger.exception(f"Loop error: {e}")
            self.status_store.mark_terminated(TerminationReason.ERROR.value)
            return TerminationReason.ERROR

    def _run_initializer_session(self) -> bool:
        """Run initializer session (session 1) using Claude Code CLI."""
        logger.info("Running initializer session")

        # Create prompt file
        prompt = create_agent_prompt(
            agent_type="initializer",
            prompts_dir=self.project_dir / "prompts",
            task_description=self.config.project.name,  # TODO: Get from task init
            project_dir=str(self.project_dir),
            plan_file=str(self.rasen_dir / "implementation_plan.json"),
            progress_file=str(self.rasen_dir / "claude-progress.txt"),
        )

        prompt_file = self.rasen_dir / "prompt_initializer.md"
        prompt_file.write_text(prompt)

        # Record commit before
        commit_before = get_current_commit(self.project_dir)

        # Run Claude Code session
        result = run_claude_session(
            prompt_file=prompt_file,
            project_dir=self.project_dir,
            timeout_seconds=self.config.orchestrator.session_timeout_seconds,
        )

        # Post-processing (relaxed for initializer)
        success = post_session_processing(
            rasen_dir=self.rasen_dir,
            project_dir=self.project_dir,
            subtask_id="init",
            session_num=self.state.iteration,
            commit_before=commit_before,
            session_exit_code=result.returncode,
            recovery_store=self.recovery_store,
            plan_store=self.plan_store,
            memory_store=self.memory_store,
            require_backpressure=False,  # Initializer doesn't need tests
        )

        return success

    def _run_coder_session(self, subtask) -> bool:
        """Run coder session (sessions 2+) using Claude Code CLI."""
        logger.info(f"Running coder session for subtask: {subtask.id}")

        # Mark subtask in progress
        self.plan_store.mark_in_progress(subtask.id)
        self.state.current_subtask_id = subtask.id

        # Update status
        self.status_store.mark_iteration_start(
            iteration=self.state.iteration,
            subtask_id=subtask.id,
            description=subtask.description,
        )

        # Get failed approaches for context
        failed_approaches = self.recovery_store.get_failed_approaches(subtask.id)

        # Get memory context
        memory_context = ""
        if self.config.memory.enabled:
            memory_context = self.memory_store.format_for_injection(
                max_tokens=self.config.memory.max_tokens
            )

        # Create prompt file
        prompt = create_agent_prompt(
            agent_type="coder",
            prompts_dir=self.project_dir / "prompts",
            subtask_id=subtask.id,
            subtask_description=subtask.description,
            failed_approaches=failed_approaches,
            memory_context=memory_context,
        )

        prompt_file = self.rasen_dir / f"prompt_coder_{subtask.id}.md"
        prompt_file.write_text(prompt)

        # Record commit before
        commit_before = get_current_commit(self.project_dir)

        # Run Claude Code session
        result = run_claude_session(
            prompt_file=prompt_file,
            project_dir=self.project_dir,
            timeout_seconds=self.config.orchestrator.session_timeout_seconds,
        )

        # Post-processing
        success = post_session_processing(
            rasen_dir=self.rasen_dir,
            project_dir=self.project_dir,
            subtask_id=subtask.id,
            session_num=self.state.iteration,
            commit_before=commit_before,
            session_exit_code=result.returncode,
            recovery_store=self.recovery_store,
            plan_store=self.plan_store,
            memory_store=self.memory_store,
            require_backpressure=True,
        )

        # Count commits (simplified - check git log)
        commits_made = 0  # TODO: Count commits from git log

        # Update status
        self.status_store.mark_iteration_end(
            commits=commits_made,
            success=success,
        )

        # Track failures
        if not success:
            self.state.consecutive_failures += 1
        else:
            self.state.consecutive_failures = 0
            self.state.total_commits += commits_made

        return success

    def _check_termination(self) -> TerminationReason | None:
        """Check all termination conditions."""
        # Max iterations
        if self.state.iteration >= self.config.orchestrator.max_iterations:
            return TerminationReason.MAX_ITERATIONS

        # Max runtime
        elapsed = (datetime.utcnow() - self.state.started_at).total_seconds()
        if elapsed >= self.config.orchestrator.max_runtime_seconds:
            return TerminationReason.MAX_RUNTIME

        # Consecutive failures
        if self.state.consecutive_failures >= self.config.stall_detection.max_consecutive_failures:
            return TerminationReason.CONSECUTIVE_FAILURES

        return None

    def _load_system_prompt(self, path: str) -> str:
        """Load system prompt from file."""
        prompt_path = self.project_dir / path
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""
```

**Acceptance Criteria:**
- [ ] Runs until completion or limit
- [ ] Distinguishes Initializer (session 1) from Coder (sessions 2+)
- [ ] Dual-confirmation before declaring complete
- [ ] Respects all termination conditions
- [ ] Updates status file every iteration
- [ ] Handles errors gracefully

**Testing:**
- Unit: Termination after max iterations
- Unit: Dual confirmation logic
- Unit: Initializer vs Coder selection
- Integration: Complete simple 3-subtask plan
- Integration: Recovery after simulated failure

**Verification:**
```python
loop = OrchestrationLoop(config, rasen_dir, project_dir)
reason = await loop.run()
assert reason in TerminationReason
```

---

### Task 4.4: Prompt Templates

**Depends on:** Task 1.1

**Description:** Prompt template loading and rendering

**Deliverables:**
- `src/rasen/prompts.py`
- `prompts/initializer.md`
- `prompts/coder.md`

**Implementation:**
```python
"""Prompt template rendering."""
from __future__ import annotations

from pathlib import Path


def render_initializer_prompt(
    task_description: str,
    project_dir: Path,
) -> str:
    """Render initializer prompt for session 1."""
    return f"""# Task Initialization

You are setting up the foundation for a long-running coding task.
This session creates everything future sessions need to work effectively.

## Your Task
{task_description}

## Working Directory
{project_dir}

## Required Outputs
1. Create `init.sh` - Script to set up development environment
2. Create `.rasen/implementation_plan.json` with ALL subtasks marked "pending"
3. Create `claude-progress.txt` - Initialize with session 1 notes
4. Make initial git commit documenting setup

## Rules
1. Break the task into 5-15 discrete subtasks
2. Each subtask should be completable in one session
3. Order subtasks by dependency (foundations first)
4. Commit all setup files before finishing

## Output Format
When complete, output:
<event topic="init.done">Created {{n}} subtasks. Ready for coding sessions.</event>
"""


def render_coder_prompt(
    subtask_id: str,
    subtask_description: str,
    failed_approaches: list[str],
    memory_context: str,
) -> str:
    """Render coder prompt for sessions 2+."""
    failed_section = ""
    if failed_approaches:
        approaches_list = "\n".join(f"- {a}" for a in failed_approaches)
        failed_section = f"""
## Previous Failed Approaches (DO NOT REPEAT)
{approaches_list}

IMPORTANT: Try a DIFFERENT approach than those listed above.
"""

    memory_section = ""
    if memory_context:
        memory_section = f"""
{memory_context}
"""

    return f"""# Coding Session

## Getting Oriented
First, understand current state:
1. Run `pwd` to confirm working directory
2. Read `claude-progress.txt` for context from previous sessions
3. Read `.rasen/implementation_plan.json` to verify current subtask
4. Check `git log --oneline -10` for recent progress

{memory_section}

## Current Task
**Subtask ID:** {subtask_id}
**Description:** {subtask_description}

{failed_section}

## CRITICAL RULES
1. Work on THIS subtask ONLY - do not start other subtasks
2. Run ALL tests before declaring done: `uv run pytest`
3. Run linter before declaring done: `uv run ruff check .`
4. Commit with message: "feat({subtask_id}): <description>"
5. Update `claude-progress.txt` with session summary

## Session End Output
When complete, output:
<event topic="build.done">tests: pass, lint: pass. <summary of what was done></event>

If blocked, output:
<event topic="build.blocked"><reason for being blocked></event>

## UNACCEPTABLE ACTIONS
- It is UNACCEPTABLE to declare completion without running tests
- It is UNACCEPTABLE to remove or modify existing tests
- It is UNACCEPTABLE to skip verification steps
- It is UNACCEPTABLE to work on multiple subtasks in one session
- It is UNACCEPTABLE to leave uncommitted work at session end
- It is UNACCEPTABLE to commit code that fails lint checks
"""
```

**Acceptance Criteria:**
- [ ] Templates render with all variables
- [ ] No unsubstituted placeholders in output
- [ ] Failed approaches injected when present
- [ ] Memory context injected when present
- [ ] Clear UNACCEPTABLE actions section

**Testing:**
- Unit: Render with all variables
- Unit: Render with empty failed approaches
- Unit: Render with empty memory context

---

## Phase 4B: Review Loop (Coder ↔ Reviewer)

**Goal:** Validate each subtask with code review before moving on

### Task 4B.1: Reviewer Session Runner

**Depends on:** Task 2.2, Task 4.4

**Description:** Read-only Reviewer agent that validates code changes

**Deliverables:**
- `src/rasen/review.py`
- `prompts/reviewer.md`

**Implementation:**
```python
"""Review loop - Coder ↔ Reviewer validation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from rasen.client import create_client, get_agent_config
from rasen.config import Config
from rasen.events import parse_events, get_event_payload
from rasen.models import Event, Subtask
from rasen.prompts import render_reviewer_prompt, render_coder_fix_prompt
from rasen.session import run_session

logger = logging.getLogger(__name__)

MAX_REVIEW_LOOPS = 3


@dataclass
class ReviewResult:
    """Result of a review session."""
    approved: bool
    feedback: str | None = None
    iteration: int = 0


async def run_review_loop(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
    rasen_dir: Path,
) -> bool:
    """
    Run Coder ↔ Reviewer loop until approved.

    1. Reviewer reviews code (read-only)
    2. If approved → return True
    3. If changes_requested → Coder fixes
    4. Loop (max 3 times)
    5. If still not approved → return False (escalate)

    Args:
        config: Configuration.
        subtask: The subtask that was just completed.
        project_dir: Path to project root.
        rasen_dir: Path to .rasen directory.

    Returns:
        True if approved, False if max loops exceeded.
    """
    for iteration in range(MAX_REVIEW_LOOPS):
        logger.info(f"Review iteration {iteration + 1}/{MAX_REVIEW_LOOPS}")

        # Run Reviewer (read-only)
        result = await _run_reviewer_session(config, subtask, project_dir)

        if result.approved:
            logger.info(f"Subtask {subtask.id} approved by reviewer")
            return True

        logger.info(f"Review requested changes: {result.feedback}")

        # If not last iteration, run Coder to fix
        if iteration < MAX_REVIEW_LOOPS - 1:
            await _run_coder_fix_session(
                config, subtask, result.feedback, project_dir
            )

    logger.warning(f"Subtask {subtask.id} not approved after {MAX_REVIEW_LOOPS} reviews")
    return False


async def _run_reviewer_session(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
) -> ReviewResult:
    """Run read-only Reviewer session."""
    # Build prompt
    prompt = render_reviewer_prompt(
        subtask_id=subtask.id,
        subtask_description=subtask.description,
        project_dir=project_dir,
    )

    # Get agent config
    agent_cfg = get_agent_config("reviewer")

    # Create client (read-only agent)
    client = create_client(config.agent, "reviewer")

    # Load system prompt
    system_prompt = _load_prompt_file("prompts/reviewer.md")

    # Run session
    result = await run_session(
        client=client,
        prompt=prompt,
        system_prompt=system_prompt,
        agent_config=config.agent,
        read_only=True,  # Reviewer cannot modify files
    )

    # Parse verdict from events
    events = result.events

    if get_event_payload(events, "review.approved"):
        return ReviewResult(approved=True)

    feedback = get_event_payload(events, "review.changes_requested")
    return ReviewResult(approved=False, feedback=feedback)


async def _run_coder_fix_session(
    config: Config,
    subtask: Subtask,
    feedback: str | None,
    project_dir: Path,
) -> None:
    """Run Coder session to fix review issues."""
    # Build prompt
    prompt = render_coder_fix_prompt(
        subtask_id=subtask.id,
        feedback=feedback or "No specific feedback provided",
        fix_type="review",
    )

    # Get agent config
    agent_cfg = get_agent_config("coder")

    # Create client
    client = create_client(config.agent, "coder")

    # Load system prompt
    system_prompt = _load_prompt_file("prompts/coder.md")

    # Run session
    await run_session(
        client=client,
        prompt=prompt,
        system_prompt=system_prompt,
        agent_config=config.agent,
    )


def _load_prompt_file(path: str) -> str:
    """Load prompt from file."""
    prompt_path = Path(path)
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""
```

**Reviewer Prompt Template (prompts/reviewer.md):**
```markdown
# Code Reviewer

You are a code reviewer validating a subtask implementation.
You have READ-ONLY access - you CANNOT modify any files.

## Your Role
- Review the code changes for the current subtask
- Check for correctness, style, and best practices
- Verify tests exist and pass
- Check for security issues

## Review Checklist
1. Does the implementation match the subtask description?
2. Are there appropriate tests for new functionality?
3. Does the code follow project conventions?
4. Are there any obvious bugs or issues?
5. Is the code readable and maintainable?

## Output Format
If the code looks good:
<event topic="review.approved">LGTM. <brief summary of what was reviewed></event>

If changes are needed:
<event topic="review.changes_requested"><specific, actionable feedback></event>

## CRITICAL RULES
- You CANNOT modify files - only review
- Be specific in feedback - vague comments are not helpful
- Focus on significant issues, not nitpicks
- If tests pass and code is correct, approve it
```

**Acceptance Criteria:**
- [ ] Reviewer runs as read-only (cannot modify files)
- [ ] Loops max 3 times before giving up
- [ ] Coder receives specific feedback to fix
- [ ] Returns True on approval, False on max loops

**Testing:**
- Unit: Mock reviewer approves immediately
- Unit: Mock reviewer requests changes, coder fixes
- Unit: Max loops exceeded returns False
- Integration: Full review loop with real agents

---

### Task 4B.2: Update Main Loop for Review

**Depends on:** Task 4B.1, Task 4.3

**Description:** Integrate review loop into main orchestration

**Implementation changes to `loop.py`:**
```python
# In OrchestrationLoop._run_coder_session(), after successful post-processing:

from rasen.review import run_review_loop

async def _run_coder_session(self, subtask) -> bool:
    """Run coder session (sessions 2+) with review loop."""
    # ... existing coder session code ...

    # Post-processing
    success = await post_session_processing(...)

    # If subtask completed, run review loop
    if success and self.config.review.enabled:
        review_approved = await run_review_loop(
            config=self.config,
            subtask=subtask,
            project_dir=self.project_dir,
            rasen_dir=self.rasen_dir,
        )

        if not review_approved:
            # Revert subtask to pending for manual review
            self.plan_store.mark_pending(subtask.id)
            logger.warning(f"Subtask {subtask.id} failed review, marked for manual review")
            return False

    return success
```

**Add to config.py:**
```python
class ReviewConfig(BaseModel):
    """Review loop settings."""
    enabled: bool = True
    max_loops: int = 3
```

**Acceptance Criteria:**
- [ ] Review loop runs after successful coder session
- [ ] Can be disabled via config (`review.enabled: false`)
- [ ] Failed reviews mark subtask for manual intervention

---

## Phase 4C: QA Loop (Coder ↔ QA)

**Goal:** Validate full implementation against acceptance criteria

### Task 4C.1: QA Session Runner

**Depends on:** Task 4B.1

**Description:** Read-only QA agent that validates acceptance criteria

**Deliverables:**
- `src/rasen/qa.py`
- `prompts/qa.md`

**Implementation:**
```python
"""QA validation loop - Coder ↔ QA until approved."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from rasen.client import create_client, get_agent_config
from rasen.config import Config
from rasen.events import get_event_payload
from rasen.models import ImplementationPlan
from rasen.prompts import render_qa_prompt, render_coder_fix_prompt
from rasen.session import run_session
from rasen.stores.plan_store import PlanStore

logger = logging.getLogger(__name__)

MAX_QA_ITERATIONS = 50
RECURRING_ISSUE_THRESHOLD = 3


@dataclass
class QAResult:
    """Result of a QA session."""
    approved: bool
    issues: list[str] = field(default_factory=list)
    iteration: int = 0


@dataclass
class QAHistory:
    """Track QA iterations for recurring issue detection."""
    iterations: list[QAResult] = field(default_factory=list)
    issue_counts: dict[str, int] = field(default_factory=dict)

    def record(self, result: QAResult) -> None:
        """Record a QA iteration."""
        self.iterations.append(result)
        for issue in result.issues:
            # Normalize issue for comparison
            key = issue.lower().strip()[:100]
            self.issue_counts[key] = self.issue_counts.get(key, 0) + 1

    def has_recurring_issues(self) -> tuple[bool, list[str]]:
        """Check if any issue has occurred 3+ times."""
        recurring = [
            issue for issue, count in self.issue_counts.items()
            if count >= RECURRING_ISSUE_THRESHOLD
        ]
        return len(recurring) > 0, recurring


async def run_qa_loop(
    config: Config,
    plan: ImplementationPlan,
    project_dir: Path,
    rasen_dir: Path,
) -> bool:
    """
    Run Coder ↔ QA loop until approved.

    Called AFTER all subtasks are complete.

    1. QA reviews against acceptance criteria (read-only)
    2. If approved → return True
    3. If rejected → Coder fixes
    4. Loop (max 50 iterations)
    5. Recurring issues (3+) → escalate to human

    Args:
        config: Configuration.
        plan: The implementation plan.
        project_dir: Path to project root.
        rasen_dir: Path to .rasen directory.

    Returns:
        True if approved, False if max loops or recurring issues.
    """
    history = QAHistory()

    for iteration in range(MAX_QA_ITERATIONS):
        logger.info(f"QA iteration {iteration + 1}/{MAX_QA_ITERATIONS}")

        # Run QA Reviewer (read-only)
        result = await _run_qa_session(config, plan, project_dir, iteration)
        result.iteration = iteration
        history.record(result)

        if result.approved:
            logger.info("QA approved - implementation complete")
            return True

        logger.info(f"QA found issues: {result.issues}")

        # Check for recurring issues
        has_recurring, recurring = history.has_recurring_issues()
        if has_recurring:
            logger.warning(f"Recurring issues detected (3+ occurrences): {recurring}")
            await _escalate_to_human(rasen_dir, recurring, iteration)
            return False

        # Run Coder to fix issues
        if iteration < MAX_QA_ITERATIONS - 1:
            await _run_coder_fix_session(
                config, plan, result.issues, project_dir
            )

    logger.warning(f"QA not approved after {MAX_QA_ITERATIONS} iterations")
    return False


async def _run_qa_session(
    config: Config,
    plan: ImplementationPlan,
    project_dir: Path,
    iteration: int,
) -> QAResult:
    """Run read-only QA session."""
    # Build prompt
    prompt = render_qa_prompt(
        task_name=plan.task_name,
        subtasks=[s.description for s in plan.subtasks],
        project_dir=project_dir,
        iteration=iteration,
    )

    # Get agent config
    agent_cfg = get_agent_config("qa")

    # Create client (read-only agent)
    client = create_client(config.agent, "qa")

    # Load system prompt
    system_prompt = _load_prompt_file("prompts/qa.md")

    # Run session
    result = await run_session(
        client=client,
        prompt=prompt,
        system_prompt=system_prompt,
        agent_config=config.agent,
        read_only=True,  # QA cannot modify files
    )

    # Parse verdict from events
    events = result.events

    if get_event_payload(events, "qa.approved"):
        return QAResult(approved=True)

    issues_payload = get_event_payload(events, "qa.rejected")
    issues = _parse_issues(issues_payload) if issues_payload else []
    return QAResult(approved=False, issues=issues)


async def _run_coder_fix_session(
    config: Config,
    plan: ImplementationPlan,
    issues: list[str],
    project_dir: Path,
) -> None:
    """Run Coder session to fix QA issues."""
    # Build prompt
    prompt = render_coder_fix_prompt(
        subtask_id="qa-fix",
        feedback="\n".join(f"- {issue}" for issue in issues),
        fix_type="qa",
    )

    # Get agent config
    agent_cfg = get_agent_config("coder")

    # Create client
    client = create_client(config.agent, "coder")

    # Load system prompt
    system_prompt = _load_prompt_file("prompts/coder.md")

    # Run session
    await run_session(
        client=client,
        prompt=prompt,
        system_prompt=system_prompt,
        agent_config=config.agent,
    )


async def _escalate_to_human(
    rasen_dir: Path,
    recurring_issues: list[str],
    iteration: int,
) -> None:
    """Create escalation file for human review."""
    escalation_file = rasen_dir / "QA_ESCALATION.md"
    content = f"""# QA Escalation - Human Review Required

## Reason
Recurring issues detected after {iteration + 1} QA iterations.
The following issues have occurred 3+ times without resolution:

## Recurring Issues
{chr(10).join(f"- {issue}" for issue in recurring_issues)}

## Recommended Actions
1. Review the implementation manually
2. Check if the acceptance criteria are realistic
3. Consider breaking the task into smaller pieces
4. Update the implementation plan if needed

## To Resume
After fixing issues manually, run: `rasen resume`
"""
    escalation_file.write_text(content)
    logger.info(f"Escalation file created: {escalation_file}")


def _parse_issues(payload: str) -> list[str]:
    """Parse issues from QA rejected payload."""
    # Split on newlines or bullet points
    lines = payload.replace("- ", "\n").split("\n")
    return [line.strip() for line in lines if line.strip()]


def _load_prompt_file(path: str) -> str:
    """Load prompt from file."""
    prompt_path = Path(path)
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""
```

**QA Prompt Template (prompts/qa.md):**
```markdown
# QA Reviewer

You are a QA engineer validating the complete implementation.
You have READ-ONLY access - you CANNOT modify any files.

## Your Role
- Validate the implementation against acceptance criteria
- Run tests and verify they pass
- Check that all subtasks are truly complete
- Identify any gaps or issues

## Validation Steps
1. Read the original task description
2. Review each completed subtask
3. Run the test suite: `uv run pytest`
4. Run the linter: `uv run ruff check .`
5. Verify the feature works as expected

## Output Format
If everything passes:
<event topic="qa.approved">All acceptance criteria met. Tests: pass, Lint: pass. <summary></event>

If issues found:
<event topic="qa.rejected">
- Issue 1: <specific description>
- Issue 2: <specific description>
</event>

## CRITICAL RULES
- You CANNOT modify files - only validate
- Be specific about what's wrong
- Include steps to reproduce issues
- Focus on acceptance criteria, not style preferences
- If tests pass and feature works, approve it
```

**Acceptance Criteria:**
- [ ] QA runs as read-only (cannot modify files)
- [ ] Loops max 50 times before giving up
- [ ] Detects recurring issues (3+ occurrences)
- [ ] Escalates to human on recurring issues
- [ ] Coder receives specific issues to fix

**Testing:**
- Unit: Mock QA approves immediately
- Unit: Mock QA rejects, coder fixes, QA approves
- Unit: Recurring issue detection triggers escalation
- Unit: Max iterations exceeded returns False
- Integration: Full QA loop with real agents

---

### Task 4C.2: Update Main Loop for QA

**Depends on:** Task 4C.1, Task 4.3

**Description:** Integrate QA loop into main orchestration

**Implementation changes to `loop.py`:**
```python
# In OrchestrationLoop.run(), after all subtasks complete:

from rasen.qa import run_qa_loop

async def run(self) -> TerminationReason:
    """Main orchestration loop with QA validation."""
    # ... existing loop code ...

    while True:
        # ... existing iteration code ...

        # Check if all subtasks complete
        if subtask is None:
            # All subtasks complete - run QA before final confirmation
            if self.config.qa.enabled and not self._qa_completed:
                logger.info("All subtasks complete, running QA validation")

                qa_approved = await run_qa_loop(
                    config=self.config,
                    plan=self.plan_store.get_plan(),
                    project_dir=self.project_dir,
                    rasen_dir=self.rasen_dir,
                )

                if qa_approved:
                    self._qa_completed = True
                    # Continue to dual-confirmation
                else:
                    # QA failed - subtasks may have been re-opened
                    logger.warning("QA validation failed")
                    continue

            # Dual confirmation
            self.state.completion_confirmations += 1
            if self.state.completion_confirmations >= 2:
                return TerminationReason.COMPLETE
```

**Add to config.py:**
```python
class QAConfig(BaseModel):
    """QA loop settings."""
    enabled: bool = True
    max_iterations: int = 50
```

**Acceptance Criteria:**
- [ ] QA loop runs after all subtasks complete
- [ ] Can be disabled via config (`qa.enabled: false`)
- [ ] QA failure allows loop to continue with reopened subtasks

---

### Task 4C.3: Prompt Template Updates

**Depends on:** Task 4B.1, Task 4C.1

**Description:** Add Coder fix prompt for review/QA issues

**Add to `src/rasen/prompts.py`:**
```python
def render_reviewer_prompt(
    subtask_id: str,
    subtask_description: str,
    project_dir: Path,
) -> str:
    """Render prompt for Reviewer agent."""
    return f"""# Code Review Request

## Subtask Under Review
**ID:** {subtask_id}
**Description:** {subtask_description}

## Working Directory
{project_dir}

## Your Task
Review the implementation of this subtask. Check:
1. Code correctness and completeness
2. Test coverage
3. Code style and conventions
4. Security considerations

## Instructions
1. Read the subtask description
2. Examine the code changes (use `git diff` or read files)
3. Run tests: `uv run pytest`
4. Run linter: `uv run ruff check .`
5. Provide your verdict

## Output
Either approve or request changes using the event format.
"""


def render_qa_prompt(
    task_name: str,
    subtasks: list[str],
    project_dir: Path,
    iteration: int,
) -> str:
    """Render prompt for QA agent."""
    subtask_list = "\n".join(f"{i+1}. {s}" for i, s in enumerate(subtasks))

    return f"""# QA Validation

## Task
{task_name}

## Completed Subtasks
{subtask_list}

## Working Directory
{project_dir}

## QA Iteration
{iteration + 1}

## Your Task
Validate the complete implementation:
1. Read the original task requirements
2. Verify each subtask is fully implemented
3. Run the full test suite
4. Check for any gaps or issues

## Instructions
1. Start by understanding what was supposed to be built
2. Examine the implementation holistically
3. Run: `uv run pytest` (all tests must pass)
4. Run: `uv run ruff check .` (no lint errors)
5. Verify the feature works as intended

## Output
Either approve or list specific issues using the event format.
"""


def render_coder_fix_prompt(
    subtask_id: str,
    feedback: str,
    fix_type: str,  # "review" or "qa"
) -> str:
    """Render prompt for Coder to fix review/QA issues."""
    source = "Code Reviewer" if fix_type == "review" else "QA Reviewer"

    return f"""# Fix Required - {source} Feedback

## Context
The {source} has identified issues that need to be fixed.

## Subtask/Context
{subtask_id}

## Issues to Fix
{feedback}

## Your Task
1. Read and understand each issue
2. Fix the issues in the code
3. Run tests to verify: `uv run pytest`
4. Run linter: `uv run ruff check .`
5. Commit your fixes

## CRITICAL RULES
- Fix ONLY the issues mentioned - don't refactor other code
- Run tests after fixing
- Commit with message: "fix({subtask_id}): address {fix_type} feedback"

## Output
<event topic="build.done">tests: pass, lint: pass. Fixed: <summary of fixes></event>
"""
```

**Acceptance Criteria:**
- [ ] All prompt templates render correctly
- [ ] Fix prompts include specific feedback
- [ ] Prompts are clear about read-only vs write access

---

## Phase 5: Git Integration

**Goal:** Safe git operations with worktree isolation

### Task 5.1: Git Operations

**Depends on:** Task 1.1

**Description:** Core git commands wrapper

**Deliverables:**
- `src/rasen/git.py`

**Implementation:**
```python
"""Git operations wrapper."""
from __future__ import annotations

import subprocess
from pathlib import Path

from rasen.exceptions import GitError


def get_current_commit(project_dir: Path) -> str:
    """Get current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get current commit: {e.stderr}") from e


def count_new_commits(project_dir: Path, since_commit: str) -> int:
    """Count commits since given hash."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{since_commit}..HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except subprocess.CalledProcessError:
        return 0


def get_current_branch(project_dir: Path) -> str:
    """Get current branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get current branch: {e.stderr}") from e


def create_branch(project_dir: Path, branch_name: str) -> None:
    """Create new branch from current HEAD."""
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to create branch: {e.stderr}") from e


def checkout_branch(project_dir: Path, branch_name: str) -> None:
    """Checkout existing branch."""
    try:
        subprocess.run(
            ["git", "checkout", branch_name],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to checkout branch: {e.stderr}") from e


def is_git_repo(project_dir: Path) -> bool:
    """Check if directory is a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=project_dir,
        capture_output=True,
    )
    return result.returncode == 0


def get_uncommitted_changes(project_dir: Path) -> bool:
    """Check if there are uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())
```

**Acceptance Criteria:**
- [ ] All operations handle errors gracefully
- [ ] Works in both main repo and worktrees
- [ ] No destructive operations without explicit intent
- [ ] Clear error messages

**Testing:**
- Unit: Each operation in test repo
- Integration: Full branch workflow

**Verification:**
```python
commit = get_current_commit(Path("."))
assert len(commit) == 40  # Full SHA
```

---

### Task 5.2: Worktree Manager

**Depends on:** Task 5.1

**Description:** Git worktree lifecycle management

**Deliverables:**
- `src/rasen/worktree.py`

**Implementation:**
```python
"""Git worktree management."""
from __future__ import annotations

import subprocess
from pathlib import Path

from rasen.config import WorktreeConfig
from rasen.exceptions import GitError


class WorktreeManager:
    """Manages git worktrees for task isolation."""

    def __init__(self, project_dir: Path, config: WorktreeConfig) -> None:
        self.project_dir = project_dir
        self.base_path = project_dir / config.base_path

    def create(self, task_name: str) -> Path:
        """
        Create isolated worktree for task.

        Args:
            task_name: Name of the task (used in path and branch).

        Returns:
            Path to worktree directory.
        """
        # Sanitize task name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_name)
        worktree_path = self.base_path / f"task-{safe_name}"
        branch_name = f"feature/{safe_name}"

        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create worktree with new branch
        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GitError(f"Failed to create worktree: {e.stderr}") from e

        return worktree_path

    def remove(self, task_name: str) -> None:
        """Remove worktree after merge/discard."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_name)
        worktree_path = self.base_path / f"task-{safe_name}"

        try:
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path)],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GitError(f"Failed to remove worktree: {e.stderr}") from e

    def list_active(self) -> list[str]:
        """List all active worktrees."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return []

        worktrees = []
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                path = line[9:]
                if str(self.base_path) in path:
                    worktrees.append(Path(path).name)

        return worktrees

    def get_worktree_path(self, task_name: str) -> Path | None:
        """Get path for existing worktree."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_name)
        worktree_path = self.base_path / f"task-{safe_name}"

        if worktree_path.exists():
            return worktree_path
        return None
```

**Acceptance Criteria:**
- [ ] Creates isolated worktree
- [ ] Creates corresponding branch
- [ ] Clean removal after completion
- [ ] Handles existing worktree gracefully
- [ ] Sanitizes task names for filesystem

**Testing:**
- Unit: Create and remove worktree
- Unit: List active worktrees
- Integration: Full workflow in worktree

**Verification:**
```python
wt = WorktreeManager(Path("."), config)
path = wt.create("auth-feature")
assert path.exists()
assert (path / ".git").exists()  # Git-linked
```

---

## Phase 6: Status & Stall Detection

**Goal:** Monitoring and stall detection for long-running operation

### Task 6.1: Status Store

**Depends on:** Task 3.2

**Description:** Write status.json every iteration for external monitoring

**Deliverables:**
- `src/rasen/stores/status_store.py`

**Implementation:**
```python
"""Real-time status tracking for monitoring."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from rasen.stores._atomic import atomic_write


class OrchestratorStatus(BaseModel):
    """Real-time status for external monitoring."""
    pid: int
    started_at: str
    iteration: int = 0
    subtask_id: str | None = None
    subtask_description: str | None = None
    subtasks_completed: int = 0
    subtasks_total: int = 0
    session_started_at: str | None = None
    last_activity_at: str
    commits_this_session: int = 0
    status: str = "starting"
    consecutive_failures: int = 0
    last_error: str | None = None
    termination_reason: str | None = None
    termination_at: str | None = None


class StatusStore:
    """Manages status file for external monitoring."""

    def __init__(self, status_file: Path) -> None:
        self.path = status_file
        self._status: OrchestratorStatus | None = None

    def mark_started(self) -> None:
        """Mark orchestrator as started."""
        now = datetime.utcnow().isoformat() + "Z"
        self._status = OrchestratorStatus(
            pid=os.getpid(),
            started_at=now,
            last_activity_at=now,
            status="running",
        )
        self._write()

    def mark_iteration_start(
        self,
        iteration: int,
        subtask_id: str,
        description: str,
    ) -> None:
        """Mark start of iteration."""
        if self._status is None:
            self.mark_started()

        now = datetime.utcnow().isoformat() + "Z"
        self._status.iteration = iteration
        self._status.subtask_id = subtask_id
        self._status.subtask_description = description
        self._status.session_started_at = now
        self._status.last_activity_at = now
        self._status.commits_this_session = 0
        self._status.status = "running"
        self._write()

    def mark_iteration_end(
        self,
        commits: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Mark end of iteration."""
        if self._status is None:
            return

        self._status.commits_this_session = commits
        self._status.last_activity_at = datetime.utcnow().isoformat() + "Z"
        self._status.last_error = error
        self._status.status = "idle"

        if not success:
            self._status.consecutive_failures += 1
        else:
            self._status.consecutive_failures = 0

        self._write()

    def mark_terminated(self, reason: str) -> None:
        """Mark orchestrator as terminated."""
        if self._status is None:
            return

        now = datetime.utcnow().isoformat() + "Z"
        self._status.status = "terminated"
        self._status.termination_reason = reason
        self._status.termination_at = now
        self._write()

    def update_progress(self, completed: int, total: int) -> None:
        """Update subtask progress."""
        if self._status is None:
            return

        self._status.subtasks_completed = completed
        self._status.subtasks_total = total
        self._write()

    def load(self) -> OrchestratorStatus | None:
        """Load status from file."""
        if not self.path.exists():
            return None
        try:
            return OrchestratorStatus.model_validate_json(self.path.read_text())
        except Exception:
            return None

    def _write(self) -> None:
        """Write status atomically."""
        if self._status is None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, self._status.model_dump_json(indent=2))
```

**Acceptance Criteria:**
- [ ] Status file written at start of each iteration
- [ ] Status file updated at end of each iteration
- [ ] Timestamps in ISO 8601 UTC format
- [ ] Atomic writes
- [ ] Termination reason recorded

**Testing:**
- Unit: Status update round-trip
- Unit: Atomic write doesn't corrupt
- Integration: Monitor during multi-session run

---

### Task 6.2: Stall Detection

**Depends on:** Task 3.3

**Description:** Detect and abort unproductive loops

**Deliverables:**
- `src/rasen/stall.py`

**Implementation:**
```python
"""Stall detection for unproductive loops."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rasen.config import StallDetectionConfig
from rasen.models import TerminationReason


@dataclass
class StallCheckResult:
    """Result of stall check."""
    is_stalled: bool
    reason: str | None
    termination_reason: TerminationReason | None


class StallDetector:
    """Multi-level stall detection."""

    def __init__(self, config: StallDetectionConfig) -> None:
        self.config = config
        self.no_commit_counts: dict[str, int] = defaultdict(int)
        self.approach_history: dict[str, list[str]] = defaultdict(list)
        self.consecutive_failures = 0

    def record_session_result(
        self,
        subtask_id: str,
        commits_made: int,
        approach: str,
        success: bool,
    ) -> StallCheckResult:
        """Record session result and check for stall."""
        # Track no-commit sessions
        if commits_made == 0:
            self.no_commit_counts[subtask_id] += 1
        else:
            self.no_commit_counts[subtask_id] = 0

        # Track failures
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

        # Track approach
        self.approach_history[subtask_id].append(approach)

        return self._check_stall(subtask_id, approach)

    def _check_stall(self, subtask_id: str, current_approach: str) -> StallCheckResult:
        """Check all stall conditions."""
        # No-commit stall
        if self.no_commit_counts[subtask_id] >= self.config.max_no_commit_sessions:
            return StallCheckResult(
                is_stalled=True,
                reason=f"NO_COMMIT_STALL: {self.no_commit_counts[subtask_id]} sessions without commits",
                termination_reason=TerminationReason.STALLED,
            )

        # Consecutive failures
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            return StallCheckResult(
                is_stalled=True,
                reason=f"CONSECUTIVE_FAILURES: {self.consecutive_failures} failures",
                termination_reason=TerminationReason.CONSECUTIVE_FAILURES,
            )

        # Circular fix detection
        if self._is_circular_fix(subtask_id, current_approach):
            return StallCheckResult(
                is_stalled=True,
                reason=f"CIRCULAR_FIX: Repeating approaches on {subtask_id}",
                termination_reason=TerminationReason.LOOP_THRASHING,
            )

        return StallCheckResult(is_stalled=False, reason=None, termination_reason=None)

    def _is_circular_fix(self, subtask_id: str, current_approach: str) -> bool:
        """Detect circular fixes using keyword similarity."""
        history = self.approach_history[subtask_id]
        if len(history) < 3:
            return False

        recent = history[-3:]
        current_keywords = self._extract_keywords(current_approach)

        similar_count = sum(
            1 for past in recent
            if self._jaccard_similarity(current_keywords, self._extract_keywords(past))
            >= self.config.circular_fix_threshold
        )

        return similar_count >= 2

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "with", "using", "trying", "attempt", "will", "should", "could",
        }
        words = text.lower().split()
        return {w for w in words if w not in stop_words and len(w) > 2}

    def _jaccard_similarity(self, set1: set[str], set2: set[str]) -> float:
        """Calculate Jaccard similarity."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def get_recovery_hints(self, subtask_id: str) -> list[str]:
        """Generate hints for agent."""
        hints = []
        history = self.approach_history.get(subtask_id, [])

        if history:
            hints.append(f"Previous attempts: {len(history)}")
            for i, approach in enumerate(history[-3:], 1):
                hints.append(f"  {i}: {approach[:100]}...")
            hints.append("Try a DIFFERENT approach.")

        if self.no_commit_counts[subtask_id] > 0:
            hints.append(f"WARNING: {self.no_commit_counts[subtask_id]} sessions without commits.")

        return hints
```

**Acceptance Criteria:**
- [ ] Detects no-commit stall (3 sessions)
- [ ] Detects consecutive failures (5)
- [ ] Detects circular fix via similarity
- [ ] Generates recovery hints
- [ ] Clear termination reason

**Testing:**
- Unit: No-commit detection
- Unit: Consecutive failure detection
- Unit: Circular fix detection
- Unit: Recovery hints generation

---

## Phase 7: Background Daemon

**Goal:** Enable multi-hour unattended operation

### Task 7.1: Daemon Manager

**Depends on:** Task 1.4

**Description:** Background process management

**Deliverables:**
- `src/rasen/daemon.py`

**Note:** Unix-only for initial release. Windows support deferred.

**Implementation:**
```python
"""Background daemon management (Unix only)."""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

from rasen.config import BackgroundConfig
from rasen.exceptions import RasenError


class DaemonManager:
    """Manages background orchestrator process."""

    def __init__(self, config: BackgroundConfig) -> None:
        self.pid_file = Path(config.pid_file)
        self.log_file = Path(config.log_file)

    def start_background(self) -> int:
        """
        Start orchestrator in background.

        Returns:
            PID of background process.

        Raises:
            RasenError: If already running or fork fails.
        """
        if sys.platform == "win32":
            raise RasenError("Background mode not supported on Windows")

        if self.is_running():
            raise RasenError(f"Already running (PID: {self.get_pid()})")

        # Ensure directories exist
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Fork
        pid = os.fork()
        if pid > 0:
            # Parent - return child PID
            return pid

        # Child - become session leader
        os.setsid()

        # Second fork
        pid = os.fork()
        if pid > 0:
            os._exit(0)

        # Write PID file
        self._write_pid()

        # Redirect output
        sys.stdout = open(self.log_file, "a", buffering=1)
        sys.stderr = sys.stdout

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGHUP, self._handle_signal)

        return os.getpid()

    def is_running(self) -> bool:
        """Check if daemon is running."""
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            self.pid_file.unlink(missing_ok=True)
            return False

    def get_pid(self) -> int | None:
        """Get PID from file."""
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, FileNotFoundError):
            return None

    def stop(self) -> bool:
        """Stop running daemon."""
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False

    def _write_pid(self) -> None:
        """Write PID file."""
        self.pid_file.write_text(str(os.getpid()))

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle termination signal."""
        self.pid_file.unlink(missing_ok=True)
        sys.exit(0)
```

**Acceptance Criteria:**
- [ ] `--background` starts detached process
- [ ] PID file written
- [ ] Log file captures output
- [ ] `stop` sends SIGTERM
- [ ] SIGHUP handled gracefully
- [ ] Stale PID detection

**Testing:**
- Unit: PID file operations
- Unit: Stale PID detection
- Integration: Start, verify, stop

---

### Task 7.2: Session Timeout

**Depends on:** Task 2.2

**Description:** Kill sessions exceeding time threshold

**Deliverables:**
- Enhancement to `src/rasen/session.py`

**Implementation:**
Add to session.py:
```python
async def run_session_with_timeout(
    client: Anthropic,
    prompt: str,
    system_prompt: str,
    agent_config: AgentConfig,
    timeout_seconds: int = 1800,
    idle_timeout_seconds: int = 300,
) -> SessionResult:
    """Run session with timeout protection."""
    import asyncio

    async def run():
        return await run_session(client, prompt, system_prompt, agent_config)

    try:
        return await asyncio.wait_for(run(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return SessionResult(
            status=SessionStatus.TIMEOUT,
            output="Session timed out",
            commits_made=0,
            events=[Event(topic="session.timeout", payload=f"Exceeded {timeout_seconds}s")],
        )
```

**Acceptance Criteria:**
- [ ] Sessions killed after timeout
- [ ] Timeout returns partial result
- [ ] Loop continues after timeout

---

## Phase 8: Testing & Documentation

**Goal:** Comprehensive tests and documentation

### Task 8.1: Unit Tests

**Depends on:** All previous tasks

**Description:** Unit tests for all modules

**Deliverables:**
- `tests/test_config.py`
- `tests/test_models.py`
- `tests/test_events.py`
- `tests/test_stores.py`
- `tests/test_validation.py`
- `tests/test_git.py`
- `tests/test_stall.py`
- `tests/test_daemon.py`

**Coverage Target:** 80%+

**Acceptance Criteria:**
- [ ] All public functions tested
- [ ] Edge cases covered
- [ ] Mocks for external dependencies
- [ ] Tests run in < 30 seconds

---

### Task 8.2: Integration Tests

**Depends on:** Task 8.1

**Description:** End-to-end workflow tests

**Deliverables:**
- `tests/integration/test_simple_task.py`
- `tests/integration/test_recovery.py`
- `tests/integration/test_worktree.py`

**Test Scenarios:**
1. Simple 3-subtask completion
2. Recovery after 2 failures
3. Worktree isolation and merge
4. Backpressure rejection and retry
5. Stall detection and abort

---

### Task 8.3: Documentation

**Depends on:** Task 8.2

**Description:** User documentation

**Deliverables:**
- `README.md` - Quick start
- `docs/configuration.md` - Config reference
- `docs/background-mode.md` - Long-running guide

---

## Summary

**Simplified Architecture:** Uses Claude Code CLI as execution engine, reducing total implementation from ~5000 lines to ~500 lines.

| Phase | Tasks | Key Deliverable | Est. Lines of Code |
|-------|-------|-----------------|-------------------|
| 0. Setup | 1 | Python project with tooling | - |
| 1. Foundation | 4 | Structure, config, models, CLI | ~150 |
| 2. **Claude Code Integration** | 3 | **CLI wrapper, prompts, events** | **~100** |
| 3. State Management | 4 | Atomic ops, plan store, recovery, memory | ~200 |
| 4. Orchestration | 4 | Processing, validation, loop, prompts | ~150 |
| **4B. Review Loop** | 2 | **Coder ↔ Reviewer loop (per subtask)** | **~50** |
| **4C. QA Loop** | 3 | **Coder ↔ QA loop (after all subtasks)** | **~50** |
| 5. Git Integration | 2 | Git operations, worktree manager | ~100 |
| 6. Status & Stall | 2 | Status store, stall detection | ~100 |
| 7. Background | 2 | Daemon manager, session timeout | ~50 |
| 8. Testing & Docs | 3 | Unit tests, integration tests, docs | ~300 |

**Total: 11 phases, 30 tasks, ~1250 lines of application code + ~300 lines of tests**

**Key Difference from Original Plan:**
- Phase 2 is now "Claude Code Integration" instead of "SDK Client Integration"
- No `anthropic` or `claude-agent-sdk` dependencies
- All AI work delegated to Claude Code CLI via `subprocess.run()`
- Dramatically simpler codebase

### Agent Summary

| Agent | Role | Modifies Code | Triggered By |
|-------|------|---------------|--------------|
| Initializer | Creates plan (session 1) | Yes | Orchestrator |
| Coder | Implements + fixes | Yes | Orchestrator, Reviewer, QA |
| Reviewer | Code review (per subtask) | **No** | After Coder completes subtask |
| QA | Validates acceptance | **No** | After all subtasks complete |

---

## Task Dependencies Graph

```
Phase 0: 0.1
           │
           ▼
Phase 1: 1.1 ──► 1.2 ──► 1.4
           │       │
           │       ▼
           └────► 1.3

Phase 2: 1.2 + 1.3 ──► 2.1 ──► 2.2
                        │
         1.3 ──────────►2.3

Phase 3: 1.1 ──► 3.2 ──► 3.1
                  │
                  ├────► 3.3
                  │
                  └────► 3.4

Phase 4: 3.1 + 3.3 ──► 4.1
         2.3 ──────────► 4.2
         4.1 + 4.2 + 2.2 ──► 4.3
         1.1 ──────────────► 4.4

Phase 4B: 2.2 + 4.4 ──► 4B.1 ──► 4B.2  (Review Loop)
                              │
                              ▼
Phase 4C: 4B.1 ──► 4C.1 ──► 4C.2 ──► 4C.3  (QA Loop)

Phase 5: 1.1 ──► 5.1 ──► 5.2

Phase 6: 3.2 ──► 6.1
         3.3 ──► 6.2

Phase 7: 1.4 ──► 7.1
         2.2 ──► 7.2

Phase 8: All ──► 8.1 ──► 8.2 ──► 8.3
```

---

## Verification Checklist (Final)

Before declaring project complete:

### Functional Requirements
- [ ] Orchestrator runs 5-subtask task to completion
- [ ] Recovery works after simulated failures
- [ ] Worktree isolation protects main branch
- [ ] Backpressure rejects incomplete work
- [ ] Memory persists and injects correctly
- [ ] Dual-confirmation prevents false completion

### Review Loop Requirements (Coder ↔ Reviewer)
- [ ] Reviewer runs after each subtask completion
- [ ] Reviewer is read-only (cannot modify files)
- [ ] Coder receives specific feedback to fix
- [ ] Max 3 review loops before escalating
- [ ] `--skip-review` flag disables review loop

### QA Loop Requirements (Coder ↔ QA)
- [ ] QA runs after ALL subtasks complete
- [ ] QA is read-only (cannot modify files)
- [ ] Coder fixes QA issues iteratively
- [ ] Max 50 QA iterations
- [ ] Recurring issues (3+) escalate to human
- [ ] QA escalation creates `QA_ESCALATION.md`
- [ ] `--skip-qa` flag disables QA loop

### Long-Running Background Requirements
- [ ] `--background` starts detached process
- [ ] Session timeout kills hung sessions (30 min)
- [ ] Status file updated every iteration
- [ ] Stall detection aborts after 3 no-commit sessions
- [ ] `rasen stop` terminates background process
- [ ] Logs capture all output in background mode

### Quality Requirements
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run mypy src/` passes
- [ ] `uv run pytest` passes
- [ ] 80%+ test coverage
