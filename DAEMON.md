# RASEN Daemon Mode - Long Running Tasks

## ✅ Fixed Issues

**Phase 7** now provides:
- ✅ **Auto-resume**: Automatically continues from where interrupted
- ✅ **Graceful shutdown**: Saves state properly on interruption
- ✅ **True background mode**: No screen/tmux needed
- ✅ **Process management**: PID tracking, signal handling

## Usage

### Start in Background

```bash
# Initialize your task
uv run rasen init --task "Implement user authentication"

# Run in background (daemon mode)
uv run rasen run --background

# Output:
# Starting daemon... (PID file: .rasen/rasen.pid, log: .rasen/rasen.log)
# Daemon started with PID 12345
```

The orchestrator now runs **completely in the background**. You can:
- Close your terminal
- Log out of SSH
- Leave it running overnight
- It keeps working!

### Monitor Progress

```bash
# Check current status
uv run rasen status
# Output:
# Status: running
# PID: 12345
# Iteration: 5
# Progress: 2/5 subtasks
# Total commits: 8
# Current subtask: auth-2
#   Implement password hashing
# Last activity: 2026-01-27T18:45:00Z

# Follow logs in real-time
uv run rasen logs --follow

# Show last 100 lines
uv run rasen logs -n 100
```

### Stop Daemon

```bash
# Graceful shutdown (waits up to 30 seconds)
uv run rasen stop

# Force kill if needed
uv run rasen stop --force
```

### Auto-Resume After Interruption

```bash
# If daemon was stopped or crashed
uv run rasen resume

# Resume in background
uv run rasen resume --background
```

**What gets preserved:**
- ✅ All completed subtasks (won't redo them)
- ✅ Implementation plan state
- ✅ Commit history
- ✅ Attempt history (failed approaches)
- ✅ Cross-session memory

**What happens:**
1. Loads saved plan from `.rasen/implementation_plan.json`
2. Skips completed subtasks
3. Continues from next pending subtask
4. Runs until complete or interrupted again

## How It Works

### Background Execution

```
rasen run --background
    ↓
Fork process (double fork for daemon)
    ↓
Detach from terminal
    ↓
Redirect stdout/stderr to .rasen/rasen.log
    ↓
Write PID to .rasen/rasen.pid
    ↓
Setup signal handlers (SIGTERM, SIGINT, SIGHUP)
    ↓
Run orchestration loop
    ↓
Clean up PID file on exit
```

### Graceful Shutdown

```
User runs: rasen stop
    ↓
Read PID from .rasen/rasen.pid
    ↓
Send SIGTERM to process
    ↓
Orchestrator receives signal
    ↓
Set shutdown flag
    ↓
Main loop checks flag at start of each iteration
    ↓
Save current state
    ↓
Exit cleanly
    ↓
Remove PID file
```

### Auto-Resume

```
User runs: rasen resume
    ↓
Check if daemon already running (prevent duplicates)
    ↓
Load .rasen/implementation_plan.json
    ↓
Show progress: "2/5 subtasks completed"
    ↓
Call: rasen run [--background]
    ↓
Orchestrator starts from next pending subtask
```

## File Structure

```
.rasen/
├── rasen.pid              # Process ID (only while running)
├── rasen.log              # Output log (background mode)
├── status.json            # Real-time progress
├── implementation_plan.json  # Subtask tracking (preserved)
├── attempt_history.json   # Recovery data (preserved)
├── good_commits.json      # Rollback targets (preserved)
└── memories.md            # Cross-session memory (preserved)
```

## Configuration

Edit `rasen.yml`:

```yaml
orchestrator:
  max_iterations: 100          # Total iterations before timeout
  max_runtime_seconds: 14400   # 4 hours max runtime
  session_delay_seconds: 3     # Delay between sessions

background:
  status_file: ".rasen/status.json"
  pid_file: ".rasen/rasen.pid"
  log_file: ".rasen/rasen.log"
```

## Signal Handling

The daemon responds to Unix signals:

| Signal | Behavior |
|--------|----------|
| SIGTERM | Graceful shutdown (saves state, exits cleanly) |
| SIGINT | Same as SIGTERM |
| SIGHUP | Reload (currently same as graceful shutdown) |
| SIGKILL | Force kill (not recommended, state not saved) |

```bash
# Graceful shutdown (recommended)
kill -TERM <PID>

# Or use the CLI (handles everything)
uv run rasen stop
```

## Examples

### Multi-Hour Task

```bash
# Start
uv run rasen init --task "Refactor entire authentication system"
uv run rasen run --background

# Check in later
uv run rasen status
# Progress: 15/20 subtasks
# Total commits: 47
# Current subtask: auth-15
# Last activity: 2026-01-27T22:15:00Z

# Follow along
uv run rasen logs --follow

# Let it finish overnight
# Check next morning:
uv run rasen status
# Status: completed
```

### Interrupted Task

```bash
# Working on long task
uv run rasen run --background

# Later: server needs reboot
uv run rasen stop
# ✅ Daemon stopped successfully

# After reboot
uv run rasen resume --background
# Resuming task: Refactor authentication system
# Progress: 8/15 subtasks completed
# Last working on: auth-9
# Daemon started with PID 23456
```

### Development Workflow

```bash
# Foreground mode for development (see output)
uv run rasen run

# When ready for long task
uv run rasen run --background

# Watch logs while working
uv run rasen logs --follow

# Stop when done
uv run rasen stop
```

## Comparison: Before vs After

### Before (Manual Workarounds)

```bash
# Required screen/tmux
screen -S rasen
uv run rasen run
# Ctrl+A D to detach

# If crashed - manual restart
screen -r rasen
uv run rasen run  # Hope it picks up correctly

# No clean shutdown
# In-progress subtask lost
```

### After (Built-in Daemon)

```bash
# Clean background mode
uv run rasen run --background

# Graceful shutdown
uv run rasen stop

# Auto-resume
uv run rasen resume --background

# Everything preserved!
```

## Troubleshooting

### Daemon Won't Start

```bash
# Check if already running
uv run rasen status

# If stale PID file
uv run rasen stop  # Cleans up automatically

# Check logs
uv run rasen logs -n 50
```

### Daemon Stopped Unexpectedly

```bash
# Check last error
uv run rasen logs | tail -50

# Resume
uv run rasen resume --background
```

### Can't Stop Daemon

```bash
# Force kill
uv run rasen stop --force

# Manual cleanup if needed
rm .rasen/rasen.pid
```

## Best Practices

1. **Use background mode for tasks > 30 minutes**
   ```bash
   uv run rasen run --background
   ```

2. **Check status periodically**
   ```bash
   watch -n 60 'uv run rasen status'
   ```

3. **Always stop gracefully**
   ```bash
   uv run rasen stop  # NOT kill -9
   ```

4. **Use resume after any interruption**
   ```bash
   uv run rasen resume --background
   ```

5. **Monitor logs for long tasks**
   ```bash
   uv run rasen logs --follow
   ```

## Technical Details

**Process Isolation:**
- Double fork to prevent zombie processes
- New session with setsid()
- Detached from controlling terminal
- stdin → /dev/null
- stdout/stderr → .rasen/rasen.log

**State Preservation:**
- Atomic file writes for all state
- Cross-platform file locking
- Status updates every iteration
- Graceful shutdown handling

**Signal Safety:**
- Signal handlers set before main loop
- Shutdown flag checked at safe points
- Clean exit with resource cleanup
- PID file removed on exit
