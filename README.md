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

Production-ready orchestrator for long-running autonomous coding tasks using Claude Code CLI as the execution engine.

## Quick Start

```bash
# Initialize task
rasen init --task "Your task description"

# Customize prompts (optional)
vi .rasen/prompts/coder.md  # Add project-specific rules

# Run orchestration
rasen run                   # Full validation (Review + QA)
rasen run --skip-review     # Skip code review (faster)
rasen run --skip-qa         # Skip QA validation
rasen run --background      # Run in background

# Monitor progress
rasen status                # Beautiful comprehensive status
rasen logs --follow         # Watch logs in real-time
```

## Features

### Core Orchestration
- **Multi-session task execution** - Break large tasks into subtasks, execute iteratively
- **Claude Code CLI integration** - Uses `claude chat --file` for all agent sessions
- **State persistence** - Atomic file operations, cross-platform file locking
- **Stall detection** - Identifies stuck sessions (3 no-commit iterations)
- **Backpressure validation** - Requires "tests: pass, lint: pass" evidence before completion

### Validation Pipeline
- **Configurable timing** - Review/QA per-subtask or after-all-subtasks (Auto-Claude pattern)
- **Review loop** - Code review validation (max 3 iterations)
- **QA loop** - Final validation against acceptance criteria (max 50 iterations)
- **Read-only validators** - Review and QA agents cannot modify files
- **Recurring issue detection** - Escalates issues that occur 3+ times
- **Human escalation** - Creates `QA_ESCALATION.md` when intervention needed

### Developer Experience
- **Session tracking** - Every log message tagged with "Session X" for easy debugging
- **Beautiful status UI** - Rich, human-readable status with progress bars and colors
- **Smart log viewing** - Auto-detects foreground/background mode
- **Per-project customization** - Customize prompts and config without rebuilding
- **Comprehensive help** - Clear help messages for all commands

### Intelligent Recovery
- **Attempt history tracking** - Records all approaches (successful and failed)
- **Failed approach injection** - Feeds past failures back to agent to avoid repetition
- **Good commit tracking** - Maintains rollback targets
- **Thrashing detection** - Identifies circular fixes (N consecutive failures)

### Cross-Session Memory
- **Markdown-based memory** - Human-readable pattern/decision/fix storage
- **Token-budgeted injection** - Injects relevant memories up to configured limit
- **Searchable by tags** - Find relevant context from past sessions

### Quality Gates
- **Test execution required** - Agent must run tests and report "pass"
- **Lint checking required** - Agent must run linter and report "pass"
- **Validation before completion** - Python-side verification of quality evidence
- **No trust, verify** - Never trusts agent claims without evidence

### Agent Architecture
Four specialized agent types with distinct roles:

| Agent | Purpose | File Access | Output Event | Loop |
|-------|---------|-------------|--------------|------|
| **Initializer** | Session 1: Create plan, init.sh | Read/Write | `init.done` | - |
| **Coder** | Implement subtasks, fix issues | Read/Write | `build.done`, `build.blocked` | Main |
| **Reviewer** | Code review (per subtask) | **Read-only** | `review.approved`, `review.changes_requested` | Review (max 3) |
| **QA** | Validate acceptance criteria | **Read-only** | `qa.approved`, `qa.rejected` | QA (max 50) |

---

## Installation

### Prerequisites

- **Python 3.12+**
- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Git**: Required for version control integration
- **uv**: Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/rasen-orchestrator
cd rasen-orchestrator

# Install dependencies
uv sync

# Verify installation
uv run rasen --version
uv run rasen --help
```

---

## Usage

### Initialize a Task

```bash
# Initialize new task
uv run rasen init --task "Implement user authentication"

# Output:
# ✅ Task initialized
#    Task: .rasen/task.txt
#    Config: .rasen/rasen-config.yml
#    Prompts: .rasen/prompts/
#    State: .rasen/
#
# 📝 Customize agent prompts in .rasen/prompts/ before running
# ⚙️  Adjust settings in .rasen/rasen-config.yml

# This creates:
# .rasen/
# ├── task.txt                 # Task description
# ├── rasen-config.yml         # Customizable settings
# ├── prompts/                 # Customizable agent prompts
# │   ├── initializer.md       # Session 1: Create plan
# │   ├── coder.md             # Implement subtasks
# │   ├── reviewer.md          # Code review
# │   └── qa.md                # QA validation
# └── status.json              # Runtime state
```

### Run Orchestration Loop

```bash
# Run with full validation pipeline
uv run rasen run
# Includes: Coder → Reviewer (per subtask) → QA (after all subtasks)

# Skip code review loop (faster iteration)
uv run rasen run --skip-review
# Only: Coder → QA

# Skip QA validation
uv run rasen run --skip-qa
# Only: Coder → Reviewer

# Minimal validation (Coder only, fastest)
uv run rasen run --skip-review --skip-qa
# Only: Coder (no validation loops)
```

### Monitor Status

```bash
# Check comprehensive status (all details in one command!)
rasen status

# Beautiful UI with:
# - Status indicator (🔄 running, ✅ complete, ❌ failed, ⏳ initialized)
# - Progress bar visualization
# - Current phase (Coding, Review, QA)
# - Session number
# - Commits count
# - Time since last activity (human-readable: "2m ago")
# - Next 3 remaining tasks preview
# - Recent activity log (last 5 entries with timestamps)
```

**Example Output:**

```
╔════════════════════════════════════════════════════════════════════╗
║  🔄  RASEN Orchestrator Status                                    ║
╠════════════════════════════════════════════════════════════════════╣
║  Status: RUNNING              PID: 12345          ║
║  Phase:  Coding               Session: 8           ║
╠════════════════════════════════════════════════════════════════════╣
║  Progress: 6/10 subtasks (60%)                            ║
║  [████████████████████████░░░░░░░░░░░░░░░░]                    ║
╠════════════════════════════════════════════════════════════════════╣
║  Current: task-7                                                ║
║  Add docstrings and type hints to fibonacci function             ║
╠════════════════════════════════════════════════════════════════════╣
║  Commits: 10                                                    ║
║  Last activity: 2m ago                                          ║
╠════════════════════════════════════════════════════════════════════╣
║  Remaining: 4 tasks                                             ║
║    1. Run full test suite and verify 100% coverage             ║
║    2. Create requirements.txt with dependencies                 ║
║    3. Create README.md with usage instructions                  ║
╠════════════════════════════════════════════════════════════════════╣
║  Recent Activity:                                               ║
║  23:05:29 │ Session 6: Working on task-6                    ║
║  23:08:20 │ Session 6: Subtask task-6 completed successful...║
║  23:08:23 │ Session 7: Working on task-7                    ║
╚════════════════════════════════════════════════════════════════════╝

💡 Tip: Use 'rasen logs --follow' to watch live updates
```

### View Logs

```bash
# View recent logs (last 50 lines)
rasen logs

# Follow logs in real-time
rasen logs --follow

# View specific number of lines
rasen logs --lines 100

# Works in both foreground and background modes:
# - Foreground: reads orchestration.log (current directory)
# - Background: reads .rasen/rasen.log (daemon log)
```

### Background Mode

For multi-hour unattended tasks:

```bash
# Run in background (daemon mode)
uv run rasen run --background

# Monitor status
uv run rasen status

# View logs in real-time
uv run rasen logs --follow

# Stop background process (graceful shutdown)
uv run rasen stop

# Resume after interruption (auto-continues from where it left off)
uv run rasen resume --background
```

**Features:**
- ✅ Runs completely detached from terminal
- ✅ Auto-resume after interruptions
- ✅ Graceful shutdown with state preservation
- ✅ Real-time status monitoring

See [Background Mode Guide](docs/background-mode.md) for complete usage details.

---

## Customization

RASEN allows full customization of agent prompts and settings **per project**. Customize before running to add project-specific instructions.

### Customize Agent Prompts

After `rasen init`, edit prompts in `.rasen/prompts/` to add project-specific rules:

**Example: Customize Coder prompt**

```bash
# Edit the coder prompt
vi .rasen/prompts/coder.md
```

Add project-specific requirements:

```markdown
# Coding Session - Subtask Implementation

## Project-Specific Rules ⚠️
- **ALWAYS use TypeScript strict mode** - no `any` types allowed
- **Error handling**: Use our custom `AppError` class, never throw raw strings
- **Logging**: Use `logger.info/warn/error`, NEVER use console.log
- **Testing**: Write unit tests in `__tests__/` directory
- **Comments**: Add JSDoc for all public functions

## Current Subtask
**ID:** {subtask_id}
**Description:** {subtask_description}
...
```

**Available Prompts:**

| Prompt | Agent | Purpose | Customization Ideas |
|--------|-------|---------|---------------------|
| `initializer.md` | Initializer | Creates implementation plan | Add complexity guidelines, subtask templates |
| `coder.md` | Coder | Implements subtasks | Add code style rules, testing requirements |
| `reviewer.md` | Reviewer | Code review validation | Add review checklist, specific concerns |
| `qa.md` | QA | Acceptance validation | Add QA criteria, edge cases to check |

**Benefits:**
- ✅ Prompts loaded **from .rasen/prompts/ first**, fallback to bundled
- ✅ **No rebuild needed** - edit anytime, changes apply immediately
- ✅ **Per-project customization** - different rules for different projects
- ✅ **Version control friendly** - commit `.rasen/` to share with team

### Customize Settings

Edit `.rasen/rasen-config.yml` to adjust orchestration behavior:

```yaml
# Agent settings
agents:
  initializer:
    prompt: prompts/initializer.md
    read_only: false
  coder:
    prompt: prompts/coder.md
    read_only: false
  reviewer:
    prompt: prompts/reviewer.md
    read_only: true      # Reviewer cannot modify files
  qa:
    prompt: prompts/qa.md
    read_only: true      # QA cannot modify files

# Session settings
session:
  timeout_seconds: 1800  # 30 minutes (increase for complex tasks)
  max_iterations: 100    # Max total iterations

# Review loop settings (Coder ↔ Reviewer)
review:
  enabled: true          # Set to false to skip code review
  per_subtask: false     # false = review after all subtasks (like Auto-Claude, faster)
                         # true = review each subtask individually (slower, catches issues early)
  max_iterations: 3      # Max review loops before escalation

# QA loop settings (Coder ↔ QA)
qa:
  enabled: true          # Set to false to skip QA validation
  per_subtask: false     # false = QA after all subtasks (recommended, like Auto-Claude)
                         # true = QA each subtask (not recommended, too slow)
  max_iterations: 50     # Max QA loops before escalation
  recurring_issue_threshold: 3  # Escalate after 3+ occurrences of same issue

# Stall detection
stall:
  max_no_commit_sessions: 3      # Abort if 3 sessions with no commits
  max_consecutive_failures: 5    # Abort after 5 consecutive failures
```

**Common Customizations:**

```yaml
# For rapid prototyping (skip validation)
review:
  enabled: false
qa:
  enabled: false

# For complex tasks (longer timeout)
session:
  timeout_seconds: 3600  # 1 hour per session

# For tight deadlines (fewer review iterations)
review:
  max_iterations: 1      # Accept after first review
```

### Workflow with Customization

```bash
# 1. Initialize task
rasen init --task "Build user auth system"

# 2. Customize prompts (add project rules)
echo "## Project Rules
- Use bcrypt for password hashing
- JWT tokens with 24h expiration
- Rate limit: 5 failed logins → lockout" >> .rasen/prompts/coder.md

# 3. Customize settings (longer timeout for auth)
vi .rasen/rasen-config.yml  # Set timeout_seconds: 3600

# 4. Run with your custom configuration
rasen run
```

**Tips:**
- 💡 Start with defaults, customize as needed
- 💡 Re-running `rasen init` **won't overwrite** existing prompts/config
- 💡 Commit `.rasen/rasen-config.yml` and `.rasen/prompts/` to share team standards
- 💡 Use `--skip-review` or `--skip-qa` flags to override config temporarily

---

## Configuration

Create `rasen.yml` in your project root (or use defaults):

```yaml
project:
  name: "my-project"
  root: "."

orchestrator:
  max_iterations: 50
  max_runtime_seconds: 14400        # 4 hours
  session_delay_seconds: 3
  session_timeout_seconds: 1800     # 30 minutes per session
  idle_timeout_seconds: 300         # 5 minutes no output = stalled

agent:
  model: "claude-sonnet-4-20250514"
  max_thinking_tokens: 4096

memory:
  enabled: true
  path: ".rasen/memories.md"
  max_tokens: 2000                   # Max tokens to inject per session

backpressure:
  require_tests: true                # Require "tests: pass" evidence
  require_lint: true                 # Require "lint: pass" evidence

stall_detection:
  max_no_commit_sessions: 3          # Abort if 3 sessions with no commits
  max_consecutive_failures: 5        # Abort after 5 consecutive failures

review:
  enabled: true                      # Run Coder ↔ Reviewer loop per subtask
  max_loops: 3                       # Max review iterations before escalating

qa:
  enabled: true                      # Run Coder ↔ QA loop after all subtasks
  max_iterations: 50                 # Max QA iterations
  recurring_issue_threshold: 3       # Escalate after 3+ occurrences
```

See `rasen.yml.example` for full configuration options, or read the [Configuration Guide](docs/configuration.md) for detailed reference.

---

## Documentation

- **[Configuration Guide](docs/configuration.md)** - Complete `rasen.yml` reference
- **[Background Mode Guide](docs/background-mode.md)** - Long-running tasks, monitoring, auto-resume
- **[DAEMON.md](DAEMON.md)** - Technical details of daemon implementation
- **[BUILD.md](BUILD.md)** - Building standalone binary with PyInstaller
- **[Implementation Plan](docs/plan.md)** - Full development roadmap
- **[Project Instructions](CLAUDE.MD)** - Coding standards and architecture

---

## Architecture

### Workflow with Validation Pipeline

```
┌────────────┐
│ Initializer│  Session 1: Creates implementation_plan.json
└─────┬──────┘
      │
      ▼ (for each subtask)
┌──────────┐     changes_requested     ┌──────────┐
│  Coder   │◄─────────────────────────►│ Reviewer │ (read-only)
│          │         approved           │          │
└────┬─────┘                            └──────────┘
     │ (max 3 review loops per subtask)
     │ (repeat for all subtasks)
     │
     ▼ (after ALL subtasks complete)
┌──────────┐         rejected           ┌──────┐
│  Coder   │◄──────────────────────────►│  QA  │ (read-only)
│          │         approved            │      │
└────┬─────┘                             └──────┘
     │ (max 50 QA iterations)
     │ (recurring issues → escalation)
     ▼
   Done ✅
```

### QA Escalation Flow

```
QA rejected (iteration 1) → Coder fixes → QA rejected (iteration 2) → Coder fixes
  ↓
QA rejected (iteration 3 with same issue)
  ↓
Recurring issue detected (threshold: 3)
  ↓
Creates QA_ESCALATION.md with:
  - List of recurring issues
  - Occurrence counts
  - Full QA history
  - Next steps for human
  ↓
Loop terminates → Human intervention required
```

### File Structure

```
.rasen/
├── rasen-config.yml              # Customizable settings (created by init)
├── task.txt                      # Task description
├── prompts/                      # Customizable agent prompts (created by init)
│   ├── initializer.md            # Session 1 prompt template
│   ├── coder.md                  # Coding session prompt template
│   ├── reviewer.md               # Code review prompt template
│   └── qa.md                     # QA validation prompt template
├── implementation_plan.json      # Subtask tracking (agent writes)
├── attempt_history.json          # Recovery tracking (orchestrator writes)
├── good_commits.json             # Rollback targets
├── memories.md                   # Cross-session memory (human-readable)
├── status.json                   # Real-time progress (for monitoring)
└── prompt_*.md                   # Rendered prompts (per session)

QA_ESCALATION.md                  # Created when QA detects recurring issues
```

---

## Development

### Code Quality

All code passes strict quality gates:

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type check (strict mode)
uv run mypy src/

# Run tests
uv run pytest

# Full quality check
uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest
```

### Project Standards

- **Python 3.12+** with type hints on all functions
- **Pydantic models** for all data structures
- **Atomic file operations** with cross-platform locking
- **Comprehensive error handling** with typed exceptions
- **Google-style docstrings** on all public APIs

See `CLAUDE.MD` for complete coding standards.

---

## How It Works

### Session Execution

1. **Orchestrator** selects next pending subtask from plan
2. **Prompt rendered** with context: subtask description, failed approaches, memory
3. **Claude Code CLI executed** via subprocess: `claude chat --file prompt.md`
4. **Agent outputs events** in XML format: `<event topic="build.done">...</event>`
5. **Orchestrator validates** completion: checks for quality evidence
6. **Review loop runs** (if enabled): Reviewer validates changes
7. **State persisted** atomically: plan updated, attempts recorded
8. **Delay enforced** (3 seconds) before next iteration
9. **QA loop runs** (if enabled, after all subtasks): validates full implementation

### Stall Detection

Three mechanisms prevent infinite loops:

1. **No-commit tracking**: 3 sessions with zero commits → abort
2. **Consecutive failures**: 5 failures in a row → abort
3. **Review/QA limits**: Max iterations before escalation

### Backpressure Validation

Agent claiming "done" must provide evidence:

```xml
<event topic="build.done">tests: pass, lint: pass. Implemented authentication.</event>
```

Orchestrator parses payload and rejects completion if missing required evidence.

### Recurring Issue Detection

QA tracks issues across iterations:

```python
# Example
Iteration 1: "Missing password validation"
Iteration 3: "Missing password validation" (2nd occurrence)
Iteration 7: "Missing password validation" (3rd occurrence)
→ Escalation triggered! Creates QA_ESCALATION.md
```

---

## Project Statistics

- **Modules**: 22 Python modules across 7 packages
- **Lines of Code**: ~3,500 (excluding comments/tests)
- **Quality**: 100% strict mypy compliance, 0 ruff errors
- **Git Commits**: 6 well-documented phases
- **Test Coverage**: TBD (Phase 8)

---

## License

MIT License - see LICENSE file for details.

## Contributing

See `docs/plan.md` for implementation roadmap. Contributions welcome!

## Acknowledgments

- **Anthropic** for Claude and Claude Code CLI
- **Auto-Claude** project for workflow patterns
- **ralph-orchestrator** for loop architecture patterns
