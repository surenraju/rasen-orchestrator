# 螺旋 RASEN - Agent Orchestrator

```
╔═══════════════════════════════════════════════════════════╗
║   螺旋  RASEN                                             ║
║   Agent Orchestrator                                      ║
║                                                           ║
║   "The spiral that never stops turning"                   ║
╚═══════════════════════════════════════════════════════════╝
```

**Name Origin:** **RA**ju + **S**ur**EN** = RASEN (螺旋 = Spiral in Japanese)

Production-ready orchestrator for long-running autonomous coding tasks using Claude Code CLI. Multi-agent workflow with intelligent validation, recovery, and human escalation.

## Why It Works

RASEN implements [Anthropic's best practices for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), applying proven patterns from production autonomous systems:

**Core Principles:**
- **Extended Two-Agent Pattern** - Separate planning (Initializer) from execution (Coder), with read-only validators (Reviewer, QA) preventing corruption
- **Fresh Context Over Compaction** - Each session starts clean, preventing context degradation over long runs
- **Single Subtask Sessions** - One task per iteration prevents scope creep and enables precise recovery
- **Intelligent Recovery** - Tracks failed approaches, detects circular fixes (30% similarity threshold), escalates recurring issues (3+ occurrences)
- **Quality Gates** - Requires explicit evidence ("tests: pass, lint: pass") before completion, no hand-waving
- **Human Escalation** - Creates `QA_ESCALATION.md` when automated recovery fails, preventing infinite loops

**Result:** Reliable multi-hour autonomous coding with graceful degradation instead of silent failures.

## Quick Start

```bash
# Initialize task
rasen init --task "Your task description"

# Customize prompts (optional)
vi .rasen/prompts/coder.md

# Run orchestration
rasen run                   # Full validation (Review + QA)
rasen run --skip-review     # Skip code review (faster)
rasen run --background      # Run in background

# Monitor progress
rasen status                # Beautiful comprehensive status
rasen logs --follow         # Watch logs in real-time
```

## Key Features

- **Multi-agent workflow** - Initializer → Coder → Reviewer → QA with read-only validators
- **Configurable validation** - Per-subtask or after-all-subtasks timing (Auto-Claude pattern)
- **Intelligent recovery** - Tracks failed approaches, detects stalls and circular fixes
- **Beautiful monitoring** - Rich status UI with progress bars, session tracking, activity log
- **Background mode** - Unattended execution with auto-resume and graceful shutdown
- **Per-project customization** - Edit prompts and config in `.rasen/` without rebuilding
- **Quality gates** - Requires "tests: pass, lint: pass" evidence before completion
- **Human escalation** - Creates `QA_ESCALATION.md` when recurring issues detected

## Agent Architecture

| Agent | Purpose | File Access | When |
|-------|---------|-------------|------|
| **Initializer** | Create plan | Read/Write | Session 1 |
| **Coder** | Implement & fix | Read/Write | All sessions |
| **Reviewer** | Code review | Read-only | Per subtask or end |
| **QA** | Validate criteria | Read-only | After all subtasks |

## Installation

**Prerequisites:** Python 3.12+, Claude Code CLI, Git, uv

```bash
# Clone repository
git clone https://github.com/surenraju/rasen-orchestrator
cd rasen-orchestrator

# Install dependencies
uv sync

# Verify installation
uv run rasen --version
```

## Basic Usage

### Initialize Task

```bash
rasen init --task "Implement user authentication"

# Creates:
# .rasen/
# ├── rasen-config.yml    # Customizable settings
# ├── prompts/            # Editable agent prompts
# │   ├── initializer.md
# │   ├── coder.md
# │   ├── reviewer.md
# │   └── qa.md
# └── status.json         # Runtime state
```

### Run Orchestration

```bash
# Foreground (full validation)
rasen run

# Background (for multi-hour tasks)
rasen run --background
rasen status              # Check progress
rasen logs --follow       # Watch logs
rasen stop                # Stop gracefully
```

### Monitor Status

Beautiful status UI with progress bars, session tracking, and activity log:

```bash
rasen status  # Shows: progress bar, current task, commits, recent activity
```

### Customize Configuration

Edit `.rasen/rasen-config.yml`:

```yaml
agents:
  reviewer:
    enabled: true
    per_subtask: false    # false = review after all subtasks (faster)
  qa:
    enabled: true
    per_subtask: false    # false = QA after all subtasks (recommended)
    max_iterations: 50
```

## Workflow

```
Initializer → creates plan (session 1)
     │
     ▼
┌─────────┐     changes_requested     ┌──────────┐
│  Coder  │◄────────────────────────►│ Reviewer │ (read-only)
└────┬────┘         approved          └──────────┘
     │ (configurable: per subtask or after all)
     │
     ▼ (after ALL subtasks complete)
┌─────────┐        rejected           ┌────┐
│  Coder  │◄────────────────────────►│ QA │ (read-only)
└─────────┘        approved           └────┘
     │ (max 50 loops, recurring issue detection)
     ▼
   Done ✅
```

## Commands

```bash
rasen init --task "description"  # Initialize new task
rasen run                        # Run orchestration (foreground)
rasen run --background           # Run in background
rasen status                     # Show comprehensive status
rasen logs --follow              # Follow logs in real-time
rasen stop                       # Stop background process
rasen resume                     # Resume after interruption
rasen --help                     # Show all commands
```

## Build

```bash
# Build standalone binary
python build.py

# Binary created at: dist/rasen
./dist/rasen --version
```

## Development

```bash
# Quality checks
uv run ruff format .      # Format
uv run ruff check .       # Lint
uv run mypy src/          # Type check
uv run pytest             # Test
```

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- **Anthropic** for Claude and Claude Code CLI
- **Auto-Claude** project for workflow patterns
- **ralph-orchestrator** for loop architecture patterns
