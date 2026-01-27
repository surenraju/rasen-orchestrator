# Ralph Orchestrator Framework - Architecture Analysis

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Source:** /ralph-orchestrator

---

## 1. Overview

**Ralph Orchestrator** is a hat-based multi-agent orchestration framework designed to keep AI agents in a continuous loop until a task is complete. Named after the Ralph Wiggum technique, it implements autonomous task completion through iterative refinement.

**Problem it Solves:**
- Orchestrates multiple AI agent backends (Claude, Kiro, Gemini, Codex, Amp) in coordinated loops
- Implements backpressure gates (tests, linting, type checks) to ensure quality work
- Maintains persistent memories and task tracking across sessions
- Provides multi-loop concurrency with git worktrees
- Supports observation-mode TUI for real-time monitoring

**Key Philosophy (The Ralph Tenets):**
1. Fresh Context Is Reliability — Clears context each iteration
2. Backpressure Over Prescription — Uses gates instead of detailed instructions
3. The Plan Is Disposable — Plans can be regenerated cheaply
4. Disk Is State, Git Is Memory — Memories and tasks are handoff mechanisms
5. Steer With Signals, Not Scripts — Let codebase guide behavior
6. Let Ralph Ralph — Observe, don't control

---

## 2. Architecture Pattern

**Pattern Type:** Multi-Agent Pub/Sub Orchestrator with Hat-Based Routing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EVENT LOOP ORCHESTRATOR                          │
├─────────────────────────────────────────────────────────────────────────┤
│  Event Bus (Pub/Sub)                                                     │
│       ↓                                                                  │
│  Hat Registry (Topic → Hat Routing)                                     │
│       ↓                                                                  │
│  Instruction Builder (Prompt Assembly)                                  │
│       ↓                                                                  │
│  Backend Execution (Claude CLI via PTY)                                 │
│       ↓                                                                  │
│  Event Parser (JSONL Output → New Events)                               │
│       ↓                                                                  │
│  Backpressure Gates (Tests, Lint, Build)                                │
└─────────────────────────────────────────────────────────────────────────┘
```

Ralph implements a **pub/sub messaging architecture** where:
- **Hats** are specialized agent personas (Planner, Builder, Reviewer, etc.)
- **Events** are messages routed through a topic-based pub/sub system
- **The Event Loop** coordinates hat selection and execution based on event topics
- **Backpressure** gates (tests, builds, lints) validate work before progression

---

## 3. Core Components

### Crate Structure (Rust Workspace)

| Crate | Purpose |
|-------|---------|
| **ralph-proto** | Shared types: Event, EventBus, Hat, HatId, Topic |
| **ralph-core** | Orchestration engine: event loop, hats, config, memories, tasks |
| **ralph-cli** | CLI interface and loop runner |
| **ralph-adapters** | Backend implementations (Claude, Kiro, Gemini, Codex, Amp) |
| **ralph-tui** | Terminal UI for observation (ratatui + crossterm) |
| **ralph-e2e** | End-to-end testing framework |
| **ralph-bench** | Benchmarking and task isolation |

### Key Modules in ralph-core

| Module | Purpose |
|--------|---------|
| `event_loop` | Main orchestrator coordinating hat selection and execution |
| `event_parser` | Parses JSONL-formatted events from agent output |
| `hat_registry` | Maintains available hats and subscription routing |
| `hatless_ralph` | Fallback orchestrator when no hat matches an event |
| `memory_store` | Persistent memories in `.agent/memories.md` |
| `task_store` | Task tracking in `.agent/tasks.jsonl` |
| `worktree` | Git worktree creation for parallel loops |

---

## 4. Agent Implementation

### Does Ralph Use Claude SDK or CLI?

**Ralph uses the Claude CLI (`claude` command), NOT the SDK:**

```rust
// Backend execution via PTY or CLI executor
let backend = CliBackend::from_config(&config.cli)?;
let mut pty_executor = PtyExecutor::new(backend.clone(), pty_config);

// Spawns: claude -p "prompt content"
// Captures streaming output in real-time
// Parses events from JSONL output
```

### Hat System (Agent Personas)

Hats are not separate processes — they're **instruction sets + event subscriptions**:

**Default Hats:**
- **Planner:** Triggers on `task.start`, `task.resume`, `build.done`, `build.blocked`
- **Builder:** Triggers on `build.task`; publishes `build.done` or `build.blocked`

**Custom Hat Definition:**
```yaml
hats:
  security-reviewer:
    subscriptions: ["review.security"]
    publishes: ["review.done", "review.blocked"]
    instructions: |
      You are a security expert. Review code for vulnerabilities.
```

**Execution Flow:**
```
1. Event loop receives "build.task" event
2. Looks up which hat subscribes to "build.task" → finds "builder" hat
3. Invokes backend with: `claude -p "instructions + event payload"`
4. Parses output for new events (e.g., "build.done")
5. Routes new events to appropriate hats
```

---

## 5. Session Management

### Fresh Context Per Iteration

Each hat invocation is a **fresh Claude process** with no context from previous iteration:
- Agents must re-read relevant files, scratchpad, memories
- Enforces "Fresh Context Is Reliability" tenet
- Prevents context corruption over long sessions

### Memory Injection

```rust
// Memories are injected into every prompt when enabled
let memories = memory_store.load()?;
let memory_markdown = format_memories_as_markdown(&memories);
let truncated = truncate_to_budget(&memory_markdown, token_budget);

prompt = format!("{}\n\n## Memories\n{}", hat_instructions, truncated);
```

### Session Resume

```bash
# Fresh start
ralph run -p "Implement feature X"

# Resume existing work
ralph run --continue  # or: ralph resume (deprecated)
```

Resume mode:
- Reads existing scratchpad
- Publishes `task.resume` instead of `task.start`
- Planner re-reads existing work instead of creating new task

---

## 6. State Persistence

### Storage Locations

| Path | Format | Purpose |
|------|--------|---------|
| `.ralph/events-*.jsonl` | JSONL | Timestamped event log for each run |
| `.ralph/current-events` | Text | Marker file pointing to active events file |
| `.agent/scratchpad.md` | Markdown | Working area for agent iterations |
| `.agent/memories.md` | Markdown | Persistent memories (Patterns, Decisions, Fixes) |
| `.agent/tasks.jsonl` | JSONL | Runtime task tracking |
| `.ralph/loop.lock` | Text | Primary loop lock (PID + prompt) |
| `.ralph/loops.json` | JSON | Registry of all active loops |
| `.worktrees/<loop-id>/` | Directory | Isolated filesystem for parallel loop |

### Termination Tracking

```rust
pub enum TerminationReason {
    CompletionPromise,    // Exit 0: Success
    MaxIterations,        // Exit 2: Limit
    MaxRuntime,           // Exit 2: Limit
    MaxCost,              // Exit 2: Limit
    ConsecutiveFailures,  // Exit 1: Error
    LoopThrashing,        // Exit 1: Error
    ValidationFailure,    // Exit 1: Error
    Stopped,              // Exit 1: Manual
    Interrupted,          // Exit 130: SIGINT
}
```

---

## 7. Workflow Phases

### Phase 1: Initialization
- Load configuration (ralph.yml)
- Set up event logger and markers
- Initialize memories and tasks
- Set up interrupt handler (Ctrl+C)

### Phase 2: Event Loop
```
1. Hat Selection — Match triggered events to subscribed hats
2. Instruction Building — Assemble prompt with:
   - Hat-specific instructions
   - Current event payload
   - Injected memories
   - Injected tasks
3. Execution — Invoke backend (Claude CLI via PTY)
4. Output Parsing — Parse for events, tool calls, completion promise
5. Backpressure Validation — Check gates (cargo test, clippy, fmt)
6. Event Publication — Emit parsed events back to event loop
```

### Phase 3: Loop Control
Check termination conditions:
- Completion promise detected (`LOOP_COMPLETE`)
- Max iterations reached
- Max runtime exceeded
- Max cost exceeded
- Consecutive failures
- User interrupt (Ctrl+C)

### Phase 4: Completion
- Publish `loop.terminate` event
- Write summary to `.agent/summary.md`
- Process merge queue for parallel loops
- Exit with appropriate code

---

## 8. Subagent Spawning (Parallel Loops)

Ralph implements **parallel loops** using **git worktrees**, not traditional subagents:

### Lock-Based Coordination

```rust
match LoopLock::try_acquire(workspace_root, &prompt_summary) {
    Ok(guard) => {
        // I'm primary — run in place
        LoopContext::primary(workspace_root)
    }
    Err(LockError::AlreadyLocked(existing)) => {
        // Create worktree and run in isolation
        create_worktree(workspace_root, &loop_id, &config)?;
        LoopContext::worktree(loop_id, worktree_path, workspace_root)
    }
}
```

### Worktree Isolation

```
main-workspace/
├── .ralph/loop.lock       ← Primary loop holds this
├── .ralph/loops.json      ← Registry of all loops
├── .ralph/merge-queue.jsonl
└── .worktrees/
    ├── loop-abc123/       ← Isolated git worktree
    │   ├── src/
    │   └── .agent/ → symlink to main
    └── loop-def456/
```

### Merge Queue (Event-Sourced)

When worktree completes:
1. Queues merge entry in `.ralph/merge-queue.jsonl`
2. Exits cleanly
3. Primary loop checks queue on completion
4. Spawns merge-ralph for each queued entry
5. Merges branch back to main

---

## 9. Configuration

### V2 Configuration Format (Current)

```yaml
cli:
  backend: claude  # auto, claude, kiro, gemini, codex, amp, custom
  default_mode: autonomous  # interactive, autonomous, tui

event_loop:
  max_iterations: 100
  prompt_file: PROMPT.md
  completion_promise: "LOOP_COMPLETE"
  max_runtime_seconds: 14400
  max_cost_usd: 50.0

core:
  scratchpad: .agent/scratchpad.md
  specs_dir: ./specs/

hats:
  builder:
    subscriptions: ["build.task"]
    publishes: ["build.done", "build.blocked"]
    instructions: |
      You are the builder. Implement one task.

memories:
  enabled: true
  filter: all  # all, context, recent

tasks:
  enabled: true

features:
  parallel: true

tui:
  enabled: true
```

### 31 Built-in Presets

```bash
ralph run --preset builtin:tdd-red-green
ralph run --preset builtin:debugging
ralph run --preset builtin:code-archaeology
```

---

## 10. Key Files

### Project Structure

```
ralph-orchestrator/
├── crates/
│   ├── ralph-proto/      # Shared types
│   ├── ralph-core/       # Orchestration engine
│   ├── ralph-cli/        # CLI interface
│   ├── ralph-adapters/   # Backend implementations
│   ├── ralph-tui/        # Terminal UI
│   ├── ralph-e2e/        # E2E testing
│   └── ralph-bench/      # Benchmarking
├── presets/              # 31 built-in presets (*.yml)
├── specs/                # Feature specifications
├── docs/                 # MkDocs documentation
├── .claude/skills/       # Claude Code skills
├── ralph.yml             # Main configuration
├── PROMPT.md             # Default prompt
└── AGENTS.md             # Development guidelines
```

### Runtime Artifacts

```
project/
├── .ralph/
│   ├── events-*.jsonl    # Event logs
│   ├── current-events    # Active events marker
│   ├── loop.lock         # Primary loop lock
│   └── merge-queue.jsonl # Parallel merge queue
├── .agent/
│   ├── scratchpad.md     # Working area
│   ├── memories.md       # Persistent memories
│   ├── tasks.jsonl       # Task tracking
│   └── summary.md        # Loop summary
└── .worktrees/           # Parallel loop worktrees
```

---

## Summary

**Ralph Orchestrator** is a sophisticated **orchestration framework** that:

| Aspect | Implementation |
|--------|----------------|
| **Agent Execution** | Claude CLI via PTY (NOT SDK) |
| **Architecture** | Pub/Sub with Hat-based routing |
| **Session Management** | Fresh context per iteration |
| **State Persistence** | JSONL events, Markdown memories, JSON tasks |
| **Parallel Execution** | Git worktrees with lock coordination |
| **Quality Gates** | Backpressure (tests, lint, build) |
| **Language** | Rust workspace (7 crates) |

**Key Differentiator:** Ralph treats the codebase itself as the instruction manual, allowing agents to learn and adapt through memories while maintaining safety through gates and iteration limits.
