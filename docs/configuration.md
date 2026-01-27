# RASEN Configuration Reference

Complete reference for `rasen.yml` configuration file.

## Quick Start

```bash
# Copy example config
cp rasen.yml.example rasen.yml

# Edit for your project
vim rasen.yml
```

## Configuration Sections

### Project Configuration

```yaml
project:
  name: "my-project"          # Project name (for display/logging)
  root: "."                   # Project root directory
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | (required) | Human-readable project name |
| `root` | string | `"."` | Path to project root directory |

**Example:**
```yaml
project:
  name: "my-web-app"
  root: "/Users/me/projects/my-web-app"
```

---

### Orchestrator Configuration

```yaml
orchestrator:
  max_iterations: 50                  # Total loop iterations before timeout
  max_runtime_seconds: 14400          # 4 hours max runtime
  session_delay_seconds: 3            # Delay between sessions
  session_timeout_seconds: 1800       # 30 min per session
  idle_timeout_seconds: 300           # 5 min no output = stalled
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_iterations` | int | `50` | Maximum orchestration loop iterations |
| `max_runtime_seconds` | int | `14400` | Total runtime limit (4 hours) |
| `session_delay_seconds` | int | `3` | Delay between Claude Code sessions |
| `session_timeout_seconds` | int | `1800` | Max time per session (30 minutes) |
| `idle_timeout_seconds` | int | `300` | Max idle time before killing session |

**When to adjust:**
- **Short tasks (<30 min):** Reduce `max_runtime_seconds` to 1800
- **Long tasks (>4 hours):** Increase `max_runtime_seconds` to 28800 (8 hours)
- **Complex sessions:** Increase `session_timeout_seconds` to 3600 (1 hour)
- **Fast iteration:** Reduce `session_delay_seconds` to 1

---

### Agent Configuration

```yaml
agent:
  model: "claude-sonnet-4-20250514"   # Claude model to use
  max_thinking_tokens: 4096           # Extended thinking tokens
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | `"claude-sonnet-4-20250514"` | Claude model identifier |
| `max_thinking_tokens` | int | `4096` | Max tokens for extended thinking |

**Available models:**
- `claude-sonnet-4-20250514` - Latest Sonnet (recommended)
- `claude-opus-4-20250514` - Opus 4 (most capable, slower)
- `claude-haiku-4-20250514` - Haiku 4 (fastest, cheaper)

**Note:** Requires Claude Code CLI configured with valid API key (`claude setup-token`)

---

### Worktree Configuration

```yaml
worktree:
  enabled: true                       # Use git worktrees for isolation
  base_path: ".worktrees"             # Where to create worktrees
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable git worktree isolation |
| `base_path` | string | `".worktrees"` | Directory for worktrees |

**How it works:**
- When enabled, each task runs in isolated git worktree
- Main branch is never touched during development
- Merge to main only when task complete
- Protects your main branch from incomplete work

**Disable when:**
- Not using git
- Working on non-git projects
- Testing/debugging locally

---

### Memory Configuration

```yaml
memory:
  enabled: true                       # Cross-session memory
  path: ".rasen/memories.md"          # Memory file location
  max_tokens: 2000                    # Max memory size
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable cross-session memory |
| `path` | string | `".rasen/memories.md"` | Memory file path |
| `max_tokens` | int | `2000` | Max memory size (approximate) |

**What gets remembered:**
- Important architectural decisions
- Patterns used (e.g., "we use Pydantic for validation")
- Failed approaches to avoid
- Key learnings from previous sessions

**Memory is injected into every Coder prompt** to maintain context consistency.

---

### Backpressure Configuration

```yaml
backpressure:
  require_tests: true                 # Require "tests: pass" evidence
  require_lint: true                  # Require "lint: pass" evidence
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `require_tests` | bool | `true` | Require test evidence in `build.done` |
| `require_lint` | bool | `true` | Require lint evidence in `build.done` |

**How backpressure works:**

Agent must emit `build.done` event with evidence:
```xml
<event topic="build.done">
Implementation complete.
tests: pass
lint: pass
</event>
```

If evidence missing, orchestrator **rejects** completion and loops again.

**When to disable:**
- Prototyping (disable `require_tests`)
- Non-code projects (disable both)
- Legacy codebase with no tests (disable `require_tests`)

---

### Background Mode Configuration

```yaml
background:
  enabled: false                      # Use --background flag to enable
  pid_file: ".rasen/rasen.pid"        # Process ID file
  log_file: ".rasen/rasen.log"        # Background log file
  status_file: ".rasen/status.json"   # Status tracking file
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable background mode |
| `pid_file` | string | `".rasen/rasen.pid"` | PID file location |
| `log_file` | string | `".rasen/rasen.log"` | Log file for background output |
| `status_file` | string | `".rasen/status.json"` | Real-time status file |

**Note:** Background mode is controlled by `--background` CLI flag, not config.

See [Background Mode Guide](background-mode.md) for usage details.

---

### Stall Detection Configuration

```yaml
stall_detection:
  max_no_commit_sessions: 3           # Abort after N sessions with no commits
  max_consecutive_failures: 5         # Abort after N consecutive failures
  circular_fix_threshold: 0.3         # 30% similarity = circular fix
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_no_commit_sessions` | int | `3` | Max sessions without commits |
| `max_consecutive_failures` | int | `5` | Max consecutive failures |
| `circular_fix_threshold` | float | `0.3` | Keyword similarity for circular fix detection |

**Stall detection triggers:**

1. **No commits for N sessions:**
   - Agent runs 3 times, makes no git commits
   - Indicates stuck/spinning without progress

2. **Consecutive failures:**
   - 5 sessions in a row fail validation
   - Indicates fundamental blocker

3. **Circular fixes:**
   - New approach is 30% similar to recent approach
   - Indicates agent is repeating failed strategies

**When stall detected:** Orchestrator aborts task and requires human intervention.

---

### Review Loop Configuration

```yaml
review:
  enabled: true                       # Run code review per subtask
  max_loops: 3                        # Max review iterations
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable Coder ↔ Reviewer loop |
| `max_loops` | int | `3` | Max review cycles before escalating |

**How review loop works:**

After each subtask completion:
1. **Reviewer agent** (read-only) reviews code
2. Emits `review.approved` or `review.changes_requested`
3. If changes requested, **Coder** fixes issues
4. Repeat up to `max_loops` times
5. After max loops, escalate to human

**Disable review when:**
- Rapid prototyping
- Non-code changes (documentation)
- Using `--skip-review` flag

---

### QA Loop Configuration

```yaml
qa:
  enabled: true                       # Run QA after all subtasks
  max_iterations: 50                  # Max QA cycles
  recurring_issue_threshold: 3        # Escalate after N occurrences
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable Coder ↔ QA loop |
| `max_iterations` | int | `50` | Max QA cycles before escalating |
| `recurring_issue_threshold` | int | `3` | Escalate recurring issues |

**How QA loop works:**

After all subtasks complete:
1. **QA agent** (read-only) validates against acceptance criteria
2. Emits `qa.approved` or `qa.rejected` with issues
3. If rejected, **Coder** fixes issues
4. Repeat up to `max_iterations` times
5. If same issue occurs 3+ times, escalate to human

**When QA escalates:**
- Creates `QA_ESCALATION.md` with details
- Orchestrator stops, requires human intervention

**Disable QA when:**
- Prototyping (use `--skip-qa` flag)
- Testing orchestrator itself
- Non-functional changes

---

## Complete Example

```yaml
# Production configuration
project:
  name: "ecommerce-platform"
  root: "/Users/dev/projects/ecommerce"

orchestrator:
  max_iterations: 100                 # Large project
  max_runtime_seconds: 28800          # 8 hours for overnight runs
  session_delay_seconds: 3
  session_timeout_seconds: 3600       # 1 hour per session (complex refactors)
  idle_timeout_seconds: 600           # 10 min idle (slow tests)

agent:
  model: "claude-sonnet-4-20250514"
  max_thinking_tokens: 4096

worktree:
  enabled: true
  base_path: ".worktrees"

memory:
  enabled: true
  path: ".rasen/memories.md"
  max_tokens: 3000                    # More context for large project

backpressure:
  require_tests: true
  require_lint: true

background:
  enabled: false
  pid_file: ".rasen/rasen.pid"
  log_file: ".rasen/rasen.log"
  status_file: ".rasen/status.json"

stall_detection:
  max_no_commit_sessions: 5           # Allow more attempts
  max_consecutive_failures: 7
  circular_fix_threshold: 0.3

review:
  enabled: true
  max_loops: 5                        # More review iterations

qa:
  enabled: true
  max_iterations: 100                 # More QA iterations
  recurring_issue_threshold: 3
```

---

## Environment-Specific Configs

### Development

```yaml
# rasen-dev.yml
orchestrator:
  max_iterations: 10                  # Fast fail
  max_runtime_seconds: 1800           # 30 min
  session_timeout_seconds: 600        # 10 min

backpressure:
  require_tests: false                # Skip for speed
  require_lint: false

review:
  enabled: false                      # Skip review

qa:
  enabled: false                      # Skip QA
```

Usage: `rasen run --config rasen-dev.yml`

### Production

```yaml
# rasen-prod.yml
orchestrator:
  max_iterations: 100
  max_runtime_seconds: 28800          # 8 hours

backpressure:
  require_tests: true                 # Strict quality
  require_lint: true

review:
  enabled: true
  max_loops: 5

qa:
  enabled: true
  max_iterations: 100
```

Usage: `rasen run --config rasen-prod.yml`

---

## Troubleshooting

### Sessions timeout too quickly

```yaml
orchestrator:
  session_timeout_seconds: 3600       # Increase to 1 hour
```

### Too many stalls

```yaml
stall_detection:
  max_no_commit_sessions: 5           # Be more lenient
```

### QA loops infinitely

```yaml
qa:
  max_iterations: 20                  # Reduce max iterations
  recurring_issue_threshold: 2        # Escalate sooner
```

### Review too strict

```yaml
review:
  max_loops: 5                        # Allow more attempts
  # Or disable: enabled: false
```

---

## Config Validation

RASEN validates config on startup:

```bash
$ rasen run
Error: Invalid config: orchestrator.max_iterations must be positive
```

**Common errors:**
- Missing required fields (`project.name`, `project.root`)
- Invalid types (string where int expected)
- Out-of-range values (negative numbers)
- File paths don't exist

---

## See Also

- [Background Mode Guide](background-mode.md) - Long-running tasks
- [DAEMON.md](../DAEMON.md) - Daemon technical details
- [README.md](../README.md) - Getting started guide
