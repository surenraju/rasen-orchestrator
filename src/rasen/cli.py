"""RASEN CLI - Command line interface."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import click

from rasen import __version__
from rasen.config import load_config
from rasen.logging import get_logger, setup_logging

logger = get_logger(__name__)


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
    """Initialize a new task with config and customizable prompts."""
    config = ctx.obj["config"]

    click.echo(f"Initializing task: {task}")
    click.echo(f"Project: {config.project.name}")
    click.echo(f"Working directory: {config.project.root}")

    # Create .rasen directory
    rasen_dir = Path(config.project.root) / ".rasen"
    rasen_dir.mkdir(parents=True, exist_ok=True)

    # Save task description (support file reference)
    task_file = rasen_dir / "task.txt"
    task_path = Path(task)
    task_content = task_path.read_text() if task_path.exists() and task_path.is_file() else task
    task_file.write_text(task_content.strip())

    # Copy agent prompts to .rasen/prompts/ for customization
    prompts_dir = rasen_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    from importlib.resources import files  # noqa: PLC0415

    prompt_templates = ["initializer.md", "coder.md", "reviewer.md", "qa.md"]
    for template_name in prompt_templates:
        bundled_prompt = files("rasen").joinpath("prompts").joinpath(template_name)
        local_prompt = prompts_dir / template_name

        # Copy if not exists (don't overwrite user customizations)
        if not local_prompt.exists():
            if hasattr(bundled_prompt, "read_text"):
                content = bundled_prompt.read_text(encoding="utf-8")
            else:
                content = Path(str(bundled_prompt)).read_text(encoding="utf-8")
            local_prompt.write_text(content)

    # Create config.yaml with default settings
    config_file = rasen_dir / "config.yaml"
    if not config_file.exists():
        config_template = """# RASEN Configuration
# Customize agent prompts and behavior in .rasen/prompts/ directory
# This file overrides settings from project-level rasen.yml

# Agent settings (model can be set per-agent)
agents:
  initializer:
    model: claude-opus-4-20250514
    prompt: prompts/initializer.md
    read_only: false

  coder:
    model: claude-opus-4-20250514
    prompt: prompts/coder.md
    read_only: false

  reviewer:
    model: claude-sonnet-4-20250514   # Sonnet for review (fast + accurate)
    prompt: prompts/reviewer.md
    read_only: true       # Reviewer cannot modify files
    enabled: true         # Enable code review
    per_subtask: false    # false = review after all subtasks (like Auto-Claude)
                          # true = review each subtask individually (slower, catches issues early)
    max_iterations: 3     # Max review loops before escalation

  qa:
    model: claude-sonnet-4-20250514   # Sonnet for QA (fast + accurate)
    prompt: prompts/qa.md
    read_only: true                # QA cannot modify files
    enabled: true                  # Enable QA validation
    per_subtask: false             # false = QA after all subtasks (recommended, like Auto-Claude)
                                   # true = QA each subtask (not recommended, too slow)
    max_iterations: 50             # Max QA loops before escalation
    recurring_issue_threshold: 3   # Escalate after N occurrences of same issue

# Session settings
session:
  timeout_seconds: 1800  # 30 minutes per session
  max_iterations: 100    # Max total iterations

# Stall detection
stall:
  max_no_commit_sessions: 3      # Abort if N sessions with no commits
  max_consecutive_failures: 5    # Abort after N consecutive failures
"""
        config_file.write_text(config_template)

    # Initialize status file
    import os  # noqa: PLC0415
    from datetime import datetime  # noqa: PLC0415

    from rasen.stores.status_store import StatusInfo, StatusStore  # noqa: PLC0415

    status_file = rasen_dir / "status.json"
    status_store = StatusStore(status_file)
    status_store.update(
        StatusInfo(
            pid=os.getpid(),
            iteration=0,
            subtask_id=None,
            subtask_description=None,
            status="initialized",
            last_activity=datetime.now(UTC),
        )
    )

    click.echo("\n✅ Task initialized")
    click.echo(f"   Task: {task_file}")
    click.echo(f"   Config: {config_file}")
    click.echo(f"   Prompts: {prompts_dir}/")
    click.echo(f"   State: {rasen_dir}/\n")
    click.echo("📝 Customize agent prompts in .rasen/prompts/ before running")
    click.echo("⚙️  Adjust settings in .rasen/config.yaml")
    click.echo("\nRun 'rasen run' to start the orchestration loop")


@main.command()
@click.option("--task", "-t", help="New task description (optional, keeps existing if not provided)")
@click.option("--keep-progress", is_flag=True, help="Keep progress.txt and metrics")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def reinit(ctx: click.Context, task: str | None, keep_progress: bool, force: bool) -> None:
    """Re-initialize to adapt to changes in task.md or prompts.

    This command:
    - Backs up current state.json to state.json.bak
    - Deletes state.json so initializer runs fresh
    - Keeps config.yaml and prompts (your customizations)
    - Optionally updates task.txt if --task provided

    Use this after updating task.md, testing.md, or other referenced docs.
    """
    import shutil  # noqa: PLC0415
    from datetime import datetime  # noqa: PLC0415

    config = ctx.obj["config"]
    project_dir = Path(config.project.root)
    rasen_dir = project_dir / ".rasen"

    if not rasen_dir.exists():
        click.echo("❌ No .rasen directory found. Run 'rasen init' first.")
        raise SystemExit(1)

    state_file = rasen_dir / "state.json"
    if not state_file.exists():
        click.echo("❌ No state.json found. Nothing to reinitialize.")
        raise SystemExit(1)

    # Confirmation
    if not force:
        click.echo("⚠️  This will reset the implementation plan and start fresh.")
        click.echo("   - state.json will be backed up and deleted")
        click.echo("   - Config and prompts will be preserved")
        if keep_progress:
            click.echo("   - progress.txt and metrics will be kept")
        else:
            click.echo("   - progress.txt and metrics will be reset")
        if not click.confirm("\nProceed with re-initialization?"):
            click.echo("Cancelled.")
            return

    # Backup state.json
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_file = rasen_dir / f"state.json.bak.{timestamp}"
    shutil.copy2(state_file, backup_file)
    click.echo(f"📦 Backed up state.json → {backup_file.name}")

    # Delete state.json
    state_file.unlink()
    click.echo("🗑️  Deleted state.json")

    # Update task.txt if provided
    if task:
        task_file = rasen_dir / "task.txt"
        task_path = Path(task)
        task_content = task_path.read_text() if task_path.exists() and task_path.is_file() else task
        task_file.write_text(task_content.strip())
        click.echo(f"📝 Updated task.txt")

    # Reset progress and metrics if not keeping
    if not keep_progress:
        progress_file = rasen_dir / "progress.txt"
        if progress_file.exists():
            progress_file.unlink()
            click.echo("🗑️  Deleted progress.txt")

        metrics_file = rasen_dir / "metrics.json"
        if metrics_file.exists():
            metrics_file.unlink()
            click.echo("🗑️  Deleted metrics.json")

        # Reset attempt history
        attempt_file = rasen_dir / "attempt_history.json"
        if attempt_file.exists():
            attempt_file.unlink()
            click.echo("🗑️  Deleted attempt_history.json")

        good_commits_file = rasen_dir / "good_commits.json"
        if good_commits_file.exists():
            good_commits_file.unlink()
            click.echo("🗑️  Deleted good_commits.json")

    # Reset status
    import os  # noqa: PLC0415

    from rasen.stores.status_store import StatusInfo, StatusStore  # noqa: PLC0415

    status_file = rasen_dir / "status.json"
    status_store = StatusStore(status_file)
    status_store.update(
        StatusInfo(
            pid=os.getpid(),
            iteration=0,
            subtask_id=None,
            subtask_description=None,
            status="reinitialized",
            last_activity=datetime.now(UTC),
        )
    )

    click.echo("\n✅ Re-initialization complete")
    click.echo("   - Preserved: config.yaml, prompts/")
    click.echo(f"   - Backup: {backup_file.name}")
    click.echo("\n🚀 Run 'rasen run' to start fresh with updated task definitions")


@main.command()
@click.option("--background", is_flag=True, help="Run in background")
@click.option("--skip-review", is_flag=True, help="Skip Coder ↔ Reviewer loop")
@click.option("--skip-qa", is_flag=True, help="Skip Coder ↔ QA loop")
@click.pass_context
def run(ctx: click.Context, background: bool, skip_review: bool, skip_qa: bool) -> None:
    """Run the orchestration loop."""
    from rasen.loop import OrchestrationLoop  # noqa: PLC0415

    config = ctx.obj["config"]

    # Override config with CLI flags
    if skip_review:
        config.review.enabled = False
    if skip_qa:
        config.qa.enabled = False

    project_dir = Path(config.project.root)
    rasen_dir = project_dir / ".rasen"
    pid_file = Path(config.background.pid_file)

    # Setup logging - always log to file
    log_file = Path(config.background.log_file) if background else rasen_dir / "orchestration.log"

    # Check if already running
    from rasen.daemon import get_daemon_status  # noqa: PLC0415

    status = get_daemon_status(pid_file)
    if status["running"]:
        click.echo(f"Daemon already running with PID {status['pid']}")
        click.echo("Use 'rasen stop' to stop it first, or 'rasen status' to check progress")
        return

    # Setup logging
    setup_logging(log_file)

    msg = (
        f"Running orchestrator (background={background}, "
        f"review={config.review.enabled}, qa={config.qa.enabled})"
    )
    click.echo(msg)

    # Handle background mode
    if background:
        from rasen.daemon import daemonize, remove_pid_file, setup_signal_handlers  # noqa: PLC0415

        click.echo(f"Starting daemon... (PID file: {pid_file}, log: {log_file})")

        try:
            daemonize(pid_file, log_file, project_dir)
        except RuntimeError as e:
            click.echo(f"Error: {e}", err=True)
            return

        # After daemonize, we're in the child process
        # The parent already exited, so this runs in background

    # Get task description from plan or task file
    from rasen.stores.plan_store import PlanStore  # noqa: PLC0415

    rasen_dir = project_dir / ".rasen"
    plan_store = PlanStore(rasen_dir)
    task_description = ""

    if plan := plan_store.load():
        # Use existing plan
        task_description = plan.task_name
    else:
        # Load from task.txt (created by init command)
        task_file = rasen_dir / "task.txt"
        if task_file.exists():
            task_description = task_file.read_text().strip()
        else:
            click.echo(
                "Error: No task found. Run 'rasen init --task \"description\"' first.",
                err=True,
            )
            ctx.exit(1)

    # Setup signal handlers if not already done (foreground mode)
    if not background:
        from rasen.daemon import setup_signal_handlers  # noqa: PLC0415

        setup_signal_handlers()

    # Run orchestration loop
    loop = OrchestrationLoop(config, project_dir, task_description)

    try:
        reason = loop.run()

        if background:
            # In background mode, log to file
            from rasen.daemon import remove_pid_file  # noqa: PLC0415

            logger.info(f"Orchestration completed: {reason.value}")
            if reason.value == "complete":
                logger.info("✅ All subtasks completed successfully!")
                if config.review.enabled:
                    logger.info("✅ Code review validation passed")
                if config.qa.enabled:
                    logger.info("✅ QA validation passed")
            remove_pid_file(pid_file)
        else:
            # In foreground mode, output to console
            click.echo(f"\nOrchestration completed: {reason.value}")
            if reason.value == "complete":
                click.echo("\n✅ All subtasks completed successfully!")
                if config.review.enabled:
                    click.echo("✅ Code review validation passed")
                if config.qa.enabled:
                    click.echo("✅ QA validation passed")

    except KeyboardInterrupt:
        if background:
            logger.info("Interrupted by user")
            from rasen.daemon import remove_pid_file  # noqa: PLC0415

            remove_pid_file(pid_file)
        else:
            click.echo("\n\nInterrupted by user")
    except Exception as e:
        if background:
            logger.exception(f"Error: {e}")
            from rasen.daemon import remove_pid_file  # noqa: PLC0415

            remove_pid_file(pid_file)
        else:
            click.echo(f"\n\nError: {e}", err=True)
            raise


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        return f"{hours}h {mins}m {secs}s"


def _format_tokens(count: int) -> str:
    """Format token count with commas."""
    return f"{count:,}"


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current status with comprehensive details."""
    import subprocess  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    from rasen.stores.metrics_store import MetricsStore  # noqa: PLC0415
    from rasen.stores.plan_store import PlanStore  # noqa: PLC0415
    from rasen.stores.status_store import StatusStore  # noqa: PLC0415

    config = ctx.obj["config"]
    project_dir = Path.cwd()
    rasen_dir = project_dir / ".rasen"
    status_file = Path(config.background.status_file)

    store = StatusStore(status_file)
    status_info = store.load()

    # Box width for consistent formatting
    box_width = 74

    if not status_info:
        click.echo("╔" + "═" * box_width + "╗")
        click.echo("║  RASEN Status" + " " * (box_width - 14) + "║")
        click.echo("╠" + "═" * box_width + "╣")
        click.echo("║  Status: Not running" + " " * (box_width - 21) + "║")
        click.echo("╚" + "═" * box_width + "╝")
        return

    # Load metrics
    metrics_store = MetricsStore(rasen_dir)
    aggregate = metrics_store.get_aggregate()

    # Calculate progress percentage
    if status_info.total_subtasks > 0:
        progress_pct = int((status_info.completed_subtasks / status_info.total_subtasks) * 100)
    else:
        progress_pct = 0

    # Progress bar
    bar_width_inner = 40
    filled = int((progress_pct / 100) * bar_width_inner)
    bar = "█" * filled + "░" * (bar_width_inner - filled)

    # Status emoji
    status_emoji = {
        "running": "🔄",
        "initialized": "⏳",
        "completed": "✅",
        "failed": "❌",
    }.get(status_info.status.split(":")[0], "❓")

    # Calculate time elapsed since last activity
    now = datetime.now(UTC)
    elapsed = now - status_info.last_activity
    if elapsed.total_seconds() < 60:
        time_ago = f"{int(elapsed.total_seconds())}s ago"
    elif elapsed.total_seconds() < 3600:
        time_ago = f"{int(elapsed.total_seconds() / 60)}m ago"
    else:
        hrs = int(elapsed.total_seconds() / 3600)
        mins = int((elapsed.total_seconds() % 3600) / 60)
        time_ago = f"{hrs}h {mins}m ago"

    # Calculate total elapsed time
    total_duration = aggregate.total_duration_seconds if aggregate.total_duration_seconds > 0 else 0
    duration_str = _format_duration(total_duration) if total_duration > 0 else "N/A"

    # Load plan for task name
    plan_store = PlanStore(rasen_dir)
    plan = plan_store.load()
    task_name = plan.task_name if plan else "Unknown task"
    if len(task_name) > 60:
        task_name = task_name[:57] + "..."

    # Print header
    click.echo("")
    click.echo("╔" + "═" * box_width + "╗")
    click.echo(f"║  {status_emoji}  RASEN Orchestrator" + " " * (box_width - 23) + "║")
    click.echo("╠" + "═" * box_width + "╣")

    # Status and started info
    status_text = status_info.status.upper()[:20]
    started_text = f"Started: {time_ago}"
    line = f"║  Status: {status_text:<20} {started_text:<30}"
    click.echo(line + " " * (box_width - len(line) + 1) + "║")

    # Task name
    task_line = f"║  Task: {task_name}"
    click.echo(task_line + " " * (box_width - len(task_line) + 1) + "║")

    # Progress section
    click.echo("╠" + "═" * box_width + "╣")
    click.echo("║  PROGRESS" + " " * (box_width - 10) + "║")

    completed = status_info.completed_subtasks
    total = status_info.total_subtasks
    progress_text = f"{completed}/{total} ({progress_pct}%)"
    bar_line = f"║  {bar}  {progress_text}"
    click.echo(bar_line + " " * (box_width - len(bar_line) + 1) + "║")

    phase_text = f"Phase: {status_info.current_phase}"
    session_text = f"Session: {status_info.iteration}"
    phase_line = f"║  {phase_text:<35} {session_text:<25}"
    click.echo(phase_line + " " * (box_width - len(phase_line) + 1) + "║")

    # Agents section
    click.echo("╠" + "═" * box_width + "╣")
    click.echo("║  AGENTS" + " " * (box_width - 8) + "║")

    # Agent table header
    click.echo("║  ┌─────────────┬──────────────────────┬──────────┬───────────┐" + " " * 8 + "║")
    click.echo("║  │ Agent       │ Model                │ Sessions │ Tokens    │" + " " * 8 + "║")
    click.echo("║  ├─────────────┼──────────────────────┼──────────┼───────────┤" + " " * 8 + "║")

    # Agent rows
    model_name = config.agent.model[:20] if hasattr(config, "agent") else "claude-sonnet-4"[:20]
    for agent_type in ["Initializer", "Coder", "Reviewer", "QA"]:
        agent_key = agent_type.lower()
        sessions = aggregate.sessions_by_agent.get(agent_key, 0)
        tokens = aggregate.tokens_by_agent.get(agent_key, 0)
        tokens_str = _format_tokens(tokens)
        row = f"║  │ {agent_type:<11} │ {model_name:<20} │ {sessions:<8} │ {tokens_str:<9} │"
        click.echo(row + " " * 8 + "║")

    click.echo("║  └─────────────┴──────────────────────┴──────────┴───────────┘" + " " * 8 + "║")

    # Metrics section
    click.echo("╠" + "═" * box_width + "╣")
    click.echo("║  METRICS" + " " * (box_width - 9) + "║")

    duration_text = f"Duration: {duration_str}"
    sessions_text = f"Total Sessions: {aggregate.total_sessions}"
    metrics_line1 = f"║  {duration_text:<35} {sessions_text:<25}"
    click.echo(metrics_line1 + " " * (box_width - len(metrics_line1) + 1) + "║")

    total_tokens_str = _format_tokens(aggregate.total_tokens)
    input_tokens_str = _format_tokens(aggregate.total_input_tokens)
    output_tokens_str = _format_tokens(aggregate.total_output_tokens)
    tokens_text = f"Tokens: {total_tokens_str} (In: {input_tokens_str} / Out: {output_tokens_str})"
    tokens_line = f"║  {tokens_text}"
    click.echo(tokens_line + " " * (box_width - len(tokens_line) + 1) + "║")

    commits_text = f"Commits: {status_info.total_commits}"
    if aggregate.total_sessions > 0:
        avg_session = _format_duration(aggregate.total_duration_seconds / aggregate.total_sessions)
    else:
        avg_session = "N/A"
    avg_text = f"Avg Session: {avg_session}"
    metrics_line2 = f"║  {commits_text:<35} {avg_text:<25}"
    click.echo(metrics_line2 + " " * (box_width - len(metrics_line2) + 1) + "║")

    # Configuration section
    click.echo("╠" + "═" * box_width + "╣")
    click.echo("║  CONFIGURATION" + " " * (box_width - 15) + "║")

    review_status = "enabled" if config.review.enabled else "disabled"
    review_mode = "(after all)" if not config.review.per_subtask else "(per subtask)"
    review_mark = "✓" if config.review.enabled else "✗"
    qa_status = "enabled" if config.qa.enabled else "disabled"
    qa_mode = "(after all)" if not config.qa.per_subtask else "(per subtask)"
    qa_mark = "✓" if config.qa.enabled else "✗"

    review_text = f"Review: {review_mark} {review_status} {review_mode}"
    qa_text = f"QA: {qa_mark} {qa_status} {qa_mode}"
    config_line1 = f"║  {review_text:<35} {qa_text:<25}"
    click.echo(config_line1 + " " * (box_width - len(config_line1) + 1) + "║")

    max_iter_text = f"Max Iterations: {config.orchestrator.max_iterations}"
    timeout_mins = config.orchestrator.session_timeout_seconds // 60
    timeout_text = f"Session Timeout: {timeout_mins}m"
    config_line2 = f"║  {max_iter_text:<35} {timeout_text:<25}"
    click.echo(config_line2 + " " * (box_width - len(config_line2) + 1) + "║")

    stall_text = f"Stall Detection: {config.stall_detection.max_no_commit_sessions} no-commit"
    fail_text = f"Consecutive Failures: {config.stall_detection.max_consecutive_failures}"
    config_line3 = f"║  {stall_text:<35} {fail_text:<25}"
    click.echo(config_line3 + " " * (box_width - len(config_line3) + 1) + "║")

    # Current section
    click.echo("╠" + "═" * box_width + "╣")
    click.echo("║  CURRENT" + " " * (box_width - 9) + "║")

    if status_info.subtask_id:
        subtask_text = f"Subtask {status_info.subtask_id}: {status_info.subtask_description or ''}"
        if len(subtask_text) > 68:
            subtask_text = subtask_text[:65] + "..."
        current_line = f"║  {subtask_text}"
        click.echo(current_line + " " * (box_width - len(current_line) + 1) + "║")

        phase_status = f"Status: {status_info.current_phase} in progress..."
        status_line = f"║  {phase_status}"
        click.echo(status_line + " " * (box_width - len(status_line) + 1) + "║")
    else:
        click.echo("║  Initializing..." + " " * (box_width - 17) + "║")

    # Recent activity section
    click.echo("╠" + "═" * box_width + "╣")
    click.echo("║  RECENT ACTIVITY" + " " * (box_width - 17) + "║")

    log_file = rasen_dir / "orchestration.log"
    if log_file.exists():
        try:
            result = subprocess.run(
                ["tail", "-n", "5", str(log_file)],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.strip().split("\n"):
                # Extract timestamp and message
                if " - " in line:
                    parts = line.split(" - ", 3)
                    if len(parts) >= 4:
                        time_part = (
                            parts[0].split()[1] if len(parts[0].split()) > 1 else parts[0][:8]
                        )
                        msg = parts[-1][:55]
                        activity_line = f"║  {time_part} │ {msg}"
                        click.echo(activity_line + " " * (box_width - len(activity_line) + 1) + "║")
        except Exception:
            click.echo("║  No recent activity" + " " * (box_width - 20) + "║")
    else:
        click.echo("║  No log file found" + " " * (box_width - 19) + "║")

    click.echo("╚" + "═" * box_width + "╝")
    click.echo("")
    click.echo("💡 Use 'rasen logs -f' to watch live | 'rasen stop' to halt")
    click.echo("")


@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", default=50, help="Number of lines to show")
@click.pass_context
def logs(ctx: click.Context, follow: bool, lines: int) -> None:
    """View orchestrator logs (supports both foreground and background modes)."""
    import subprocess  # noqa: PLC0415

    config = ctx.obj["config"]
    project_dir = Path.cwd()
    rasen_dir = project_dir / ".rasen"

    # Check for foreground log first (orchestration.log in .rasen/)
    foreground_log = rasen_dir / "orchestration.log"
    daemon_log = Path(config.background.log_file)

    # Determine which log file to use
    log_file = None
    log_mode = None

    if foreground_log.exists():
        log_file = foreground_log
        log_mode = "foreground"
    elif daemon_log.exists():
        log_file = daemon_log
        log_mode = "background"

    if not log_file:
        click.echo("No log file found.")
        click.echo("Logs are created when you run:")
        click.echo("  - Foreground: 'rasen run' (creates .rasen/orchestration.log)")
        click.echo("  - Background: 'rasen run --background' (creates .rasen/rasen.log)")
        return

    if follow:
        mode_label = "foreground" if log_mode == "foreground" else "background (daemon)"
        click.echo(f"Following {mode_label} log: {log_file}")
        click.echo("Press Ctrl+C to stop")
        click.echo("─" * 70)
        try:
            # Use tail -f to follow log
            subprocess.run(["tail", "-f", str(log_file)], check=False)
        except KeyboardInterrupt:
            click.echo("\n\nStopped following log")
    else:
        # Show last N lines
        try:
            result = subprocess.run(
                ["tail", "-n", str(lines), str(log_file)],
                capture_output=True,
                text=True,
                check=True,
            )
            mode_label = "Foreground" if log_mode == "foreground" else "Background (daemon)"
            click.echo(f"─── {mode_label} Log (last {lines} lines) ───")
            click.echo(result.stdout)
        except subprocess.CalledProcessError:
            click.echo("Error reading log file", err=True)


@main.command()
@click.option("--force", is_flag=True, help="Force kill if graceful shutdown fails")
@click.pass_context
def stop(ctx: click.Context, force: bool) -> None:
    """Stop background orchestrator."""
    from rasen.daemon import get_daemon_status, stop_daemon  # noqa: PLC0415

    config = ctx.obj["config"]
    pid_file = Path(config.background.pid_file)

    status = get_daemon_status(pid_file)

    if not status["running"]:
        if status.get("stale"):
            click.echo("Daemon not running (stale PID file found, cleaning up)")
            from rasen.daemon import remove_pid_file  # noqa: PLC0415

            remove_pid_file(pid_file)
        else:
            click.echo("No daemon running")
        return

    click.echo(f"Stopping daemon with PID {status['pid']}...")

    timeout = 10 if force else 30
    if stop_daemon(pid_file, timeout=timeout):
        click.echo("✅ Daemon stopped successfully")
    else:
        click.echo("❌ Failed to stop daemon", err=True)


@main.command()
@click.option("--background", is_flag=True, help="Resume in background")
@click.pass_context
def resume(ctx: click.Context, background: bool) -> None:
    """Resume after interruption.

    This automatically picks up from where the orchestrator left off.
    All completed subtasks are preserved, and execution continues from
    the next pending subtask.
    """
    from rasen.daemon import get_daemon_status  # noqa: PLC0415
    from rasen.stores.plan_store import PlanStore  # noqa: PLC0415
    from rasen.stores.status_store import StatusStore  # noqa: PLC0415

    config = ctx.obj["config"]
    project_dir = Path(config.project.root)
    pid_file = Path(config.background.pid_file)

    # Check if already running
    status_check = get_daemon_status(pid_file)
    if status_check["running"]:
        click.echo(f"Daemon already running with PID {status_check['pid']}")
        click.echo("Use 'rasen status' to check progress")
        return

    # Check if there's a plan to resume
    plan_store = PlanStore(project_dir / ".rasen")
    plan = plan_store.load()

    if not plan:
        click.echo("No task to resume. Use 'rasen init' to start a new task.")
        return

    # Check status
    status_store = StatusStore(Path(config.background.status_file))
    status_info = status_store.load()

    if status_info:
        completed, total = plan_store.get_completion_stats()
        click.echo(f"Resuming task: {plan.task_name}")
        click.echo(f"Progress: {completed}/{total} subtasks completed")

        if status_info.subtask_id:
            click.echo(f"Last working on: {status_info.subtask_id}")
    else:
        click.echo(f"Resuming task: {plan.task_name}")

    # Resume by calling run command
    ctx.invoke(run, background=background, skip_review=False, skip_qa=False)


@main.command()
@click.pass_context
def merge(ctx: click.Context) -> None:  # noqa: ARG001
    """Merge completed worktree."""
    click.echo("Merge command")
    # Implementation in later task


if __name__ == "__main__":
    main()
