# Background Mode - Long-Running Tasks Guide

Complete guide to running RASEN in background mode for multi-hour unattended tasks.

## Overview

RASEN can run tasks that take **hours or days** to complete by running as a background daemon process. This mode is designed for:

- Complex refactoring tasks (2-8 hours)
- Multi-feature implementations (4-24 hours)
- Large migrations (1-3 days)
- Overnight autonomous development

**Key Features:**
- ✅ Runs completely detached from terminal
- ✅ Auto-resume after interruptions
- ✅ Real-time progress monitoring
- ✅ Graceful shutdown with state preservation
- ✅ Comprehensive logging

---

## Quick Start

```bash
# Initialize task
uv run rasen init --task "Implement user authentication system"

# Run in background
uv run rasen run --background

# Check status anytime
uv run rasen status

# View logs
uv run rasen logs --follow

# Stop when done
uv run rasen stop
```

---

## When to Use Background Mode

| Scenario | Mode | Why |
|----------|------|-----|
| Quick fix (<30 min) | Foreground | See output immediately |
| Feature development (1-2 hours) | Foreground or Background | Your preference |
| Large refactor (2-8 hours) | **Background** | Don't tie up terminal |
| Multi-feature (>8 hours) | **Background** | Run overnight/weekend |
| CI/CD integration | **Background** | Automated workflows |

---

## Basic Usage

### Starting Background Task

```bash
# Option 1: Start directly in background
uv run rasen init --task "Your task description"
uv run rasen run --background

# Option 2: Initialize, then run
uv run rasen init --task "Refactor authentication layer"
# Do other work...
uv run rasen run --background
```

**Output:**
```
Starting daemon... (PID file: .rasen/rasen.pid, log: .rasen/rasen.log)
Daemon started with PID 12345
```

**What happens:**
1. Process forks and detaches from terminal
2. PID written to `.rasen/rasen.pid`
3. All output redirected to `.rasen/rasen.log`
4. Status updates written to `.rasen/status.json`
5. You can close terminal, log out, etc.

---

### Checking Status

```bash
uv run rasen status
```

**Example output:**
```
Status: running
PID: 12345
Iteration: 15/50
Progress: 3/7 subtasks completed
Total commits: 24
Current subtask: auth-4
  Description: Implement password reset flow
Last activity: 2026-01-27T18:45:00Z
Runtime: 2h 15m
```

**Status values:**
- `running` - Currently executing
- `completed` - Task finished successfully
- `failed` - Task failed (check logs)
- `interrupted` - Stopped mid-execution (can resume)
- `not_running` - No background process

---

### Viewing Logs

```bash
# View last 50 lines
uv run rasen logs

# View last 100 lines
uv run rasen logs -n 100

# Follow logs in real-time (like tail -f)
uv run rasen logs --follow

# View with grep
uv run rasen logs | grep ERROR
```

**Log format:**
```
2026-01-27 18:45:23 - INFO - Iteration 15/50
2026-01-27 18:45:24 - INFO - Working on subtask: auth-4
2026-01-27 18:46:15 - INFO - Session completed: 2 commits
2026-01-27 18:46:18 - INFO - Running review loop...
2026-01-27 18:47:02 - INFO - Review approved
2026-01-27 18:47:02 - INFO - Subtask auth-4 completed
```

---

### Stopping Background Task

```bash
# Graceful shutdown (waits for current session to finish)
uv run rasen stop

# Force kill immediately
uv run rasen stop --force
```

**Graceful shutdown:**
- Waits up to 30 seconds for current session to complete
- Saves all state (plan, progress, memories)
- Cleans up PID file
- Safe to resume later

**Force kill:**
- Immediately terminates process
- State may be incomplete
- Use only if graceful shutdown hangs

---

## Auto-Resume After Interruption

If background task is interrupted (server reboot, crash, manual stop), you can **resume exactly where it left off**.

### How to Resume

```bash
uv run rasen resume

# Or resume in background again
uv run rasen resume --background
```

**Example:**
```bash
$ uv run rasen resume
Resuming task: Implement user authentication
Progress: 3/7 subtasks completed
Last working on: auth-4
  Description: Implement password reset flow

Starting from next pending subtask: auth-5
```

**What gets preserved:**
- ✅ All completed subtasks (won't redo)
- ✅ Implementation plan state
- ✅ Git commit history
- ✅ Failed attempt history
- ✅ Cross-session memory
- ✅ QA feedback

**What resumes:**
- Continues from next pending subtask
- Reloads context from memories
- Applies backpressure validation
- Runs until complete or interrupted again

---

## Configuration for Long Tasks

Edit `rasen.yml` for optimal long-running performance:

```yaml
orchestrator:
  max_iterations: 100                 # More iterations for large tasks
  max_runtime_seconds: 28800          # 8 hours (overnight run)
  session_timeout_seconds: 3600       # 1 hour per session
  idle_timeout_seconds: 600           # 10 min idle timeout

background:
  pid_file: ".rasen/rasen.pid"
  log_file: ".rasen/rasen.log"
  status_file: ".rasen/status.json"

stall_detection:
  max_no_commit_sessions: 5           # Be lenient for complex tasks
  max_consecutive_failures: 7
```

**For overnight runs:**
```yaml
orchestrator:
  max_runtime_seconds: 43200          # 12 hours
  session_timeout_seconds: 5400       # 90 min per session
```

See [Configuration Guide](configuration.md) for full reference.

---

## Monitoring Long Tasks

### External Monitoring Script

```bash
#!/bin/bash
# monitor-rasen.sh - Check status every 5 minutes

while true; do
  echo "=== $(date) ==="
  cd /path/to/project
  uv run rasen status
  echo ""
  sleep 300  # 5 minutes
done
```

Usage:
```bash
chmod +x monitor-rasen.sh
./monitor-rasen.sh
```

### Watch Command

```bash
# Update status every 60 seconds
watch -n 60 'cd /path/to/project && uv run rasen status'
```

### Log Monitoring

```bash
# Watch for errors
tail -f .rasen/rasen.log | grep -i error

# Count commits in real-time
watch -n 30 'git log --oneline | wc -l'
```

---

## Status File Structure

`.rasen/status.json` is updated every iteration for external monitoring:

```json
{
  "pid": 12345,
  "status": "running",
  "iteration": 15,
  "max_iterations": 50,
  "subtask_id": "auth-4",
  "subtask_description": "Implement password reset flow",
  "completed_subtasks": 3,
  "total_subtasks": 7,
  "total_commits": 24,
  "last_activity": "2026-01-27T18:45:00Z",
  "started_at": "2026-01-27T16:30:00Z"
}
```

**Use cases:**
- CI/CD pipelines check status programmatically
- External dashboards display progress
- Alerting systems monitor for failures

---

## Advanced Patterns

### CI/CD Integration

```yaml
# .github/workflows/rasen.yml
name: Autonomous Development

on:
  workflow_dispatch:
    inputs:
      task:
        description: 'Task description'
        required: true

jobs:
  rasen:
    runs-on: ubuntu-latest
    timeout-minutes: 480  # 8 hours
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: pip install uv

      - name: Run RASEN
        run: |
          uv run rasen init --task "${{ inputs.task }}"
          uv run rasen run --background

          # Monitor until completion
          while [ "$(uv run rasen status --format json | jq -r .status)" = "running" ]; do
            echo "Progress: $(uv run rasen status --format json | jq .completed_subtasks)/$(uv run rasen status --format json | jq .total_subtasks)"
            sleep 60
          done

      - name: Check results
        run: |
          if [ "$(uv run rasen status --format json | jq -r .status)" = "completed" ]; then
            echo "✅ Task completed successfully"
            exit 0
          else
            echo "❌ Task failed"
            uv run rasen logs
            exit 1
          fi
```

### Overnight Development Workflow

```bash
# Evening: Start long task
uv run rasen init --task "Refactor entire API layer"
uv run rasen run --background

# Check it started
uv run rasen status

# Go home / sleep

# Morning: Check results
uv run rasen status
# Status: completed
# Progress: 15/15 subtasks completed
# Total commits: 87

# Review changes
git log --oneline -20

# If good, merge
uv run rasen merge
```

### Multi-Day Tasks with Checkpoints

```bash
# Day 1: Start major refactor
uv run rasen init --task "Migrate from REST to GraphQL"
uv run rasen run --background

# Day 1 End: Check progress
uv run rasen status
# Progress: 8/20 subtasks

# Day 2 Morning: Resume (auto-continues)
uv run rasen status
# Still running from Day 1

# If stopped overnight:
uv run rasen resume --background

# Day 2 End: Should be complete
uv run rasen status
# Status: completed
```

---

## Troubleshooting

### Daemon Won't Start

```bash
# Check if already running
uv run rasen status

# If stale PID file
rm .rasen/rasen.pid
uv run rasen run --background

# Check for errors
uv run rasen logs -n 100
```

### Task Stalled

```bash
# Check logs for clues
uv run rasen logs | tail -100

# If stuck, stop and resume
uv run rasen stop
uv run rasen resume --background
```

### Lost Track of Background Process

```bash
# Find process by name
ps aux | grep rasen

# Or check PID file
cat .rasen/rasen.pid

# Get status
uv run rasen status

# If orphaned, kill manually
kill $(cat .rasen/rasen.pid)
rm .rasen/rasen.pid
```

### Out of Disk Space

Background tasks generate logs and state files:

```bash
# Check log file size
ls -lh .rasen/rasen.log

# Truncate if too large (loses history)
> .rasen/rasen.log

# Or rotate
mv .rasen/rasen.log .rasen/rasen.log.old
```

---

## Best Practices

### 1. Start with Foreground Mode

Test your task in foreground first:

```bash
# Test run (see output immediately)
uv run rasen run --skip-review --skip-qa

# If works well, use background for real run
uv run rasen run --background
```

### 2. Monitor Early Iterations

```bash
# Start in background
uv run rasen run --background

# Watch first few iterations
uv run rasen logs --follow

# Once stable, detach (Ctrl+C)
```

### 3. Set Realistic Timeouts

```yaml
# For 2-hour task
orchestrator:
  max_runtime_seconds: 10800          # 3 hours (50% buffer)

# For overnight (8 hours expected)
orchestrator:
  max_runtime_seconds: 43200          # 12 hours (50% buffer)
```

### 4. Use Checkpointing for Very Long Tasks

For tasks >12 hours, split into phases:

```bash
# Phase 1: Foundation (4 hours)
uv run rasen init --task "Phase 1: Implement core models"
uv run rasen run --background
# Wait for completion...

# Phase 2: Business logic (6 hours)
uv run rasen init --task "Phase 2: Implement business logic"
uv run rasen run --background
# Wait for completion...

# Phase 3: API layer (4 hours)
uv run rasen init --task "Phase 3: Implement API endpoints"
uv run rasen run --background
```

### 5. Review Before Merging

Even with QA loops, always review:

```bash
# Task completed
uv run rasen status
# Status: completed

# Review changes
git log --stat
git diff main..rasen-feature

# Test manually
pytest

# If good, merge
uv run rasen merge
```

---

## Performance Expectations

| Task Size | Subtasks | Expected Runtime | Commits | Config |
|-----------|----------|------------------|---------|--------|
| Small feature | 3-5 | 30-60 min | 5-10 | Default |
| Medium feature | 5-10 | 1-3 hours | 10-25 | Default |
| Large refactor | 10-20 | 3-8 hours | 25-75 | Extended timeouts |
| Major migration | 20-50 | 8-24 hours | 75-200 | Extended + checkpoints |

**Factors affecting runtime:**
- Model used (Sonnet vs Opus vs Haiku)
- Code complexity
- Test suite size
- Review strictness
- Number of review/QA iterations

---

## Security Considerations

### Background Tasks Run with Your Permissions

The daemon runs as your user:
- Can read/write any files you can
- Can execute commands you can
- Uses your git credentials
- Uses your Claude API key

**Recommendations:**
- Run in isolated directory
- Use git worktrees (default)
- Review changes before merging
- Monitor resource usage

### Protect Sensitive Files

Add to `.gitignore`:
```
.rasen/
.worktrees/
```

Never commit:
- `.rasen/status.json` (may contain PII)
- `.rasen/rasen.log` (verbose output)
- `.rasen/memories.md` (project-specific context)

---

## See Also

- [Configuration Guide](configuration.md) - Tuning for long tasks
- [DAEMON.md](../DAEMON.md) - Technical implementation details
- [README.md](../README.md) - Getting started
- [Auto-Resume](../DAEMON.md#auto-resume-after-interruption) - Recovery details
