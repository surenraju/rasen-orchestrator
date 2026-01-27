# Ralph-Claude-Code Framework - Architecture Analysis

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Source:** /ralph-claude-code

---

## 1. Overview

**Ralph-Claude-Code** is a bash-based autonomous development loop orchestrator that keeps Claude Code running continuously until a task is complete, with intelligent exit detection and cost control.

**Problem it Solves:**
- Automates continuous AI development loops
- Prevents runaway costs with rate limiting and circuit breakers
- Maintains session context across iterations
- Detects stagnation and completion signals
- Provides observability through comprehensive logging

**Key Statistics:**
- 424 tests (100% pass rate)
- 11 unit test files, 4 integration test files
- Phase 1 complete (CLI modernization)
- Production-ready since v0.10.0

---

## 2. Architecture Pattern

**Pattern Type:** Single-Agent Loop Orchestrator with Circuit Breaker

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RALPH-CLAUDE-CODE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  CLI        │ →  │  Loop       │ →  │  Claude     │                  │
│  │  Interface  │    │  Orchestrator│   │  Code CLI   │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         ↓                  ↓                  ↓                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Config     │    │  Circuit    │    │  Response   │                  │
│  │  (.ralphrc) │    │  Breaker    │    │  Analyzer   │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         ↓                  ↓                  ↓                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Session    │    │  Rate       │    │  Exit       │                  │
│  │  Manager    │    │  Limiter    │    │  Detector   │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Principle:** Ralph orchestrates a **single focused Claude instance** per loop iteration, not multiple agents. Each iteration is a fresh context with session continuity via `--continue` flag.

---

## 3. Core Components

### Script Structure

```
ralph-claude-code/
├── ralph_loop.sh           # Main loop orchestrator (~1,200 LOC)
├── ralph_monitor.sh        # Live tmux dashboard
├── setup.sh                # Project initialization
├── ralph_import.sh         # PRD converter
├── ralph_enable.sh         # Interactive wizard
├── ralph_enable_ci.sh      # CI version
├── install.sh              # Global installation
├── lib/
│   ├── response_analyzer.sh  # JSON parsing, completion detection
│   ├── circuit_breaker.sh    # Stagnation detection
│   ├── enable_core.sh        # Enable logic
│   ├── task_sources.sh       # Task import (beads, GitHub, PRD)
│   ├── wizard_utils.sh       # Interactive prompts
│   ├── date_utils.sh         # Cross-platform dates
│   └── timeout_utils.sh      # Timeout handling
└── templates/
    ├── PROMPT.md             # Agent instructions
    ├── fix_plan.md           # Task list
    └── AGENT.md              # Build instructions
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `ralph_loop.sh` | Main orchestration loop |
| `response_analyzer.sh` | JSON parsing, session management, exit detection |
| `circuit_breaker.sh` | Three-state pattern (CLOSED/OPEN/HALF_OPEN) |
| `enable_core.sh` | Project detection, template generation |
| `task_sources.sh` | Import from beads, GitHub, PRD |

---

## 4. Agent Implementation

### Does Ralph Use SDK or CLI?

**Ralph uses the Claude CLI (`claude` command):**

```bash
# Build Claude command with modern CLI flags
claude -p "$prompt_content" \
  --output-format json \
  --allowed-tools Write,Read,Edit,Bash \
  --continue  # Session continuity
```

**Minimum Version:** 2.0.76

### Single-Agent Model

Ralph doesn't implement multi-agent systems. Each loop iteration:
1. Reads PROMPT.md (agent instructions)
2. Injects loop context (iteration, tasks, circuit breaker state)
3. Executes Claude Code with session continuity
4. Analyzes response and updates state
5. Continues or exits based on conditions

### Context Injection

```
---LOOP_CONTEXT---
LOOP_NUMBER: 5
MAX_CALLS_PER_HOUR: 100
CALLS_REMAINING: 45
CIRCUIT_BREAKER_STATE: CLOSED
RECENT_WORK: "Implemented API authentication"
REMAINING_TASKS: [incomplete task list]
---END_LOOP_CONTEXT---
```

---

## 5. Session Management

### Session Lifecycle

```
START → NEW SESSION
  ↓
LOOP 1: Use --continue flag (resume session)
  ↓
LOOP 2: Maintain continuity (Claude remembers context)
  ↓
END CONDITIONS TRIGGER RESET:
  - Circuit breaker opens
  - Manual interrupt (Ctrl+C)
  - Project completion
  - Session expiration (24 hours)
  - Manual reset (--reset-session)
```

### Session Storage

**Primary:** `.ralph/.claude_session_id`
```json
{
  "session_id": "uuid-v4-string",
  "created_at": "2026-01-27T10:30:00Z",
  "last_used": "2026-01-27T12:45:00Z",
  "expires_at": "2026-01-28T10:30:00Z"
}
```

**History:** `.ralph/.ralph_session_history` (last 50 transitions)

### Session Functions

| Function | Purpose |
|----------|---------|
| `init_session_tracking()` | Initialize session files |
| `store_session_id()` | Save with timestamp |
| `get_last_session_id()` | Retrieve stored session |
| `should_resume_session()` | Check 24-hour expiration |
| `reset_session()` | Clear session and exit signals |

---

## 6. State Persistence

### State Files

| File | Purpose | Format |
|------|---------|--------|
| `.ralph/status.json` | Current loop status | JSON |
| `.ralph/progress.json` | Project progress | JSON |
| `.ralph/.circuit_breaker_state` | Circuit breaker | JSON |
| `.ralph/.response_analysis` | Last response analysis | JSON |
| `.ralph/.exit_signals` | Exit signal tracking | JSON |
| `.ralph/.call_count` | Rate limiting | JSON |
| `.ralph/logs/loop_N.log` | Per-loop logs | Text |

### Status JSON Example

```json
{
  "loop_count": 5,
  "status": "running",
  "calls_made_this_hour": 23,
  "max_calls_per_hour": 100,
  "circuit_breaker_state": "CLOSED",
  "last_work_type": "IMPLEMENTATION",
  "timestamp": "2026-01-27T10:45:00Z"
}
```

### Response Analysis

```json
{
  "analysis": {
    "status": "IN_PROGRESS",
    "exit_signal": false,
    "work_type": "IMPLEMENTATION",
    "files_modified": 3,
    "test_status": "PASSING",
    "completion_indicators": 1,
    "confidence_score": 75
  }
}
```

---

## 7. Workflow Phases

### Loop Cycle

```
LOOP START
  ↓
LOAD CONFIGURATION (.ralphrc)
  ↓
LOAD SESSION (if valid)
  ↓
BUILD CLAUDE COMMAND
  ├─ Set output format (json)
  ├─ Set allowed tools
  ├─ Set session continuity (--continue)
  └─ Inject loop context
  ↓
EXECUTE CLAUDE CODE
  ├─ Run with timeout (15 min default)
  ├─ Capture JSON output
  └─ Record execution
  ↓
ANALYZE RESPONSE
  ├─ Parse JSON (array/object/flat formats)
  ├─ Extract completion indicators
  ├─ Two-stage error filtering
  └─ Confidence scoring
  ↓
UPDATE STATE
  ├─ Record loop metrics
  ├─ Update circuit breaker
  └─ Track rate limits
  ↓
EVALUATE EXIT CONDITIONS
  ├─ All tasks complete?
  ├─ completion_indicators >= 2 AND EXIT_SIGNAL == true?
  ├─ Circuit breaker open?
  └─ Rate limit exceeded?
  ↓
CONTINUE OR EXIT
```

### Work Types

| Type | Frequency | Description |
|------|-----------|-------------|
| IMPLEMENTATION | 60-70% | Building features |
| TESTING | 15-20% | Running tests |
| DOCUMENTATION | 10-15% | Writing docs |
| REFACTORING | 5-10% | Code cleanup |
| DEBUGGING | Variable | Fixing issues |

---

## 8. Subagent Spawning

**Ralph does NOT implement subagent spawning.**

Ralph orchestrates a single Claude instance per iteration. The PROMPT.md template mentions subagents aspirationally:
> "Use parallel subagents for complex tasks (max 100 concurrent)"

This depends on Claude Code's capabilities, not Ralph's orchestration.

### Task Decomposition Alternative

Ralph encourages task decomposition through:
- `.ralph/fix_plan.md` - Prioritized checklist
- Context injection - Each loop knows what's complete
- Feedback loop - Claude reports progress

---

## 9. Configuration

### Three-Level Hierarchy (Priority Order)

1. **Environment variables** (highest)
2. **.ralphrc** (project-specific)
3. **CLI flags**
4. **Ralph defaults** (lowest)

### CLI Flags

```bash
ralph [OPTIONS]
  -c, --calls NUM         # Max calls/hour (default: 100)
  -p, --prompt FILE       # Custom prompt file
  -t, --timeout MIN       # Timeout (1-120 min, default: 15)
  --output-format FORMAT  # json or text
  --allowed-tools TOOLS   # Comma-separated
  --no-continue           # Disable session continuity
  --reset-circuit         # Reset circuit breaker
  --reset-session         # Reset session
```

### .ralphrc Configuration

```bash
# PROJECT
PROJECT_NAME="my-project"
PROJECT_TYPE="typescript"

# LOOP SETTINGS
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"

# SESSION
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=24

# CIRCUIT BREAKER
CB_NO_PROGRESS_THRESHOLD=3
CB_SAME_ERROR_THRESHOLD=5
CB_OUTPUT_DECLINE_THRESHOLD=70
```

---

## 10. Key Files

### Main Scripts

| File | Purpose | LOC |
|------|---------|-----|
| `ralph_loop.sh` | Main orchestrator | ~1,200 |
| `ralph_monitor.sh` | tmux dashboard | ~200 |
| `setup.sh` | Project init | ~100 |
| `ralph_import.sh` | PRD converter | ~400 |
| `ralph_enable.sh` | Interactive wizard | ~500 |

### Library Modules

| File | Purpose |
|------|---------|
| `response_analyzer.sh` | JSON parsing, session management |
| `circuit_breaker.sh` | Stagnation detection |
| `enable_core.sh` | Project detection |
| `task_sources.sh` | Import from external sources |

### Project Structure

```
.ralph/
├── PROMPT.md           # Agent instructions
├── fix_plan.md         # Task checklist
├── AGENT.md            # Build instructions
├── status.json         # Loop status
├── progress.json       # Project progress
├── .claude_session_id  # Session tracking
├── .circuit_breaker_state
├── .response_analysis
├── .exit_signals
└── logs/
    ├── ralph.log
    └── loop_N.log
```

---

## 11. Key Algorithms

### Dual-Condition Exit Gate

```bash
# Requires BOTH conditions:
# 1. completion_indicators >= 2
# 2. EXIT_SIGNAL == true (explicit from Claude)

if [[ $recent_completion_indicators -ge 2 ]] && \
   [[ "$claude_exit_signal" == "true" ]]; then
    return 0  # Exit
fi
```

**Rationale:** Prevents false exits when Claude uses completion words naturally.

### Two-Stage Error Filtering

```bash
# Stage 1: Filter JSON field false positives
filtered=$(echo "$output" | grep -v '"[^"]*error[^"]*":')

# Stage 2: Detect actual errors
error_count=$(echo "$filtered" | grep -cE '(^Error:|Exception|Fatal)')
```

**Rationale:** Eliminates false positives from JSON fields like `"is_error": false`.

### Circuit Breaker States

```
CLOSED → Normal operation
  ↓ (no progress for 3 loops)
OPEN → Stop execution
  ↓ (after cooldown)
HALF_OPEN → Probe with single loop
  ↓ (if successful)
CLOSED
```

---

## Summary

**Ralph-Claude-Code** is a **single-agent loop orchestrator** that:

| Aspect | Implementation |
|--------|----------------|
| **Agent Execution** | Claude CLI with `--continue` |
| **Architecture** | Single-agent loop with circuit breaker |
| **Session Management** | JSON files + 24-hour expiration |
| **State Persistence** | JSON state files + log rotation |
| **Parallel Execution** | None (single agent) |
| **Quality Gates** | Circuit breaker + rate limiting |
| **Language** | Bash (424 tests) |

**Key Differentiator:** Dual-condition exit gate (completion indicators + explicit EXIT_SIGNAL) prevents false positives while respecting Claude's explicit intent about completion status.

**Production Status:** v0.11.1, Phase 1 complete, 424 tests passing.
