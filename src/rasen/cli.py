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

    # Save task description
    task_file = rasen_dir / "task.txt"
    task_file.write_text(task.strip())

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
    read_only: true       # Reviewer cannot modify files
    enabled: true         # Enable code review
    per_subtask: false    # false = review after all subtasks (like Auto-Claude)
                          # true = review each subtask individually (slower, catches issues early)
    max_iterations: 3     # Max review loops before escalation

  qa:
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
    pid_file = Path(config.background.pid_file)

    # Setup logging - always log to file
    log_file = Path(config.background.log_file) if background else project_dir / "orchestration.log"

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


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current status with comprehensive details."""
    import subprocess  # noqa: PLC0415
    from datetime import datetime  # noqa: PLC0415

    from rasen.stores.plan_store import PlanStore  # noqa: PLC0415
    from rasen.stores.status_store import StatusStore  # noqa: PLC0415

    config = ctx.obj["config"]
    project_dir = Path.cwd()
    rasen_dir = project_dir / ".rasen"
    status_file = Path(config.background.status_file)

    store = StatusStore(status_file)
    status_info = store.load()

    if not status_info:
        click.echo("╔════════════════════════════════════════════════════════╗")
        click.echo("║  RASEN Status                                          ║")
        click.echo("╠════════════════════════════════════════════════════════╣")
        click.echo("║  Status: Not running                                   ║")
        click.echo("╚════════════════════════════════════════════════════════╝")
        return

    # Calculate progress percentage
    if status_info.total_subtasks > 0:
        progress_pct = int((status_info.completed_subtasks / status_info.total_subtasks) * 100)
    else:
        progress_pct = 0

    # Progress bar
    bar_width = 40
    filled = int((progress_pct / 100) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)

    # Status emoji
    status_emoji = {
        "running": "🔄",
        "initialized": "⏳",
        "complete": "✅",
        "failed": "❌",
    }.get(status_info.status, "❓")

    # Calculate time elapsed
    now = datetime.now(UTC)
    elapsed = now - status_info.last_activity
    if elapsed.total_seconds() < 60:
        time_ago = f"{int(elapsed.total_seconds())}s ago"
    elif elapsed.total_seconds() < 3600:
        time_ago = f"{int(elapsed.total_seconds() / 60)}m ago"
    else:
        time_ago = f"{int(elapsed.total_seconds() / 3600)}h ago"

    # Print header
    click.echo("\n╔════════════════════════════════════════════════════════════════════╗")
    click.echo(f"║  {status_emoji}  RASEN Orchestrator Status" + " " * 36 + "║")
    click.echo("╠════════════════════════════════════════════════════════════════════╣")

    # Status and PID
    click.echo(f"║  Status: {status_info.status.upper():<20} PID: {status_info.pid:<15}║")
    click.echo(f"║  Phase:  {status_info.current_phase:<20} Session: {status_info.iteration:<12}║")
    click.echo("╠════════════════════════════════════════════════════════════════════╣")

    # Progress
    completed = status_info.completed_subtasks
    total = status_info.total_subtasks
    progress_text = f"{completed}/{total} subtasks ({progress_pct}%)"
    padding = " " * (47 - len(progress_text))
    click.echo(f"║  Progress: {progress_text}{padding}║")
    click.echo(f"║  [{bar}]" + " " * (64 - len(bar) - 4) + "║")
    click.echo("╠════════════════════════════════════════════════════════════════════╣")

    # Current task
    if status_info.subtask_id:
        click.echo(f"║  Current: {status_info.subtask_id:<54}║")
        desc = status_info.subtask_description or ""
        if len(desc) > 60:
            desc = desc[:57] + "..."
        click.echo(f"║  {desc:<64}║")
    else:
        click.echo("║  Current: Initializing..." + " " * 41 + "║")

    click.echo("╠════════════════════════════════════════════════════════════════════╣")

    # Git info
    click.echo(f"║  Commits: {status_info.total_commits:<54}║")

    # Last activity
    click.echo(f"║  Last activity: {time_ago:<48}║")
    click.echo("╠════════════════════════════════════════════════════════════════════╣")

    # Load plan to show remaining tasks
    plan_store = PlanStore(rasen_dir / "implementation_plan.json")
    if plan := plan_store.load():
        pending_tasks = [s for s in plan.subtasks if s.status.value == "pending"]
        if pending_tasks:
            remaining_text = f"{len(pending_tasks)} tasks"
            padding = " " * (54 - len(remaining_text))
            click.echo(f"║  Remaining: {remaining_text}{padding}║")
            # Show next 3 tasks
            for i, task in enumerate(pending_tasks[:3], 1):
                desc = task.description
                task_desc = desc[:55] if len(desc) > 55 else desc
                click.echo(f"║    {i}. {task_desc:<59}║")
        else:
            click.echo("║  Remaining: No pending tasks" + " " * 36 + "║")

    click.echo("╠════════════════════════════════════════════════════════════════════╣")

    # Recent log entries (last 5 lines)
    log_file = rasen_dir.parent / "orchestration.log"
    if log_file.exists():
        try:
            result = subprocess.run(
                ["tail", "-n", "5", str(log_file)],
                capture_output=True,
                text=True,
                check=True,
            )
            click.echo("║  Recent Activity:" + " " * 47 + "║")
            for line in result.stdout.strip().split("\n"):
                # Extract timestamp and message
                if " - " in line:
                    parts = line.split(" - ", 3)
                    if len(parts) >= 4:
                        time_part = parts[0].split()[1]  # Get time only
                        msg = parts[-1][:55]
                        click.echo(f"║  {time_part} │ {msg:<48}║")
        except Exception:
            pass

    click.echo("╚════════════════════════════════════════════════════════════════════╝")
    click.echo("\n💡 Tip: Use 'rasen logs --follow' to watch live updates\n")


@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", default=50, help="Number of lines to show")
@click.pass_context
def logs(ctx: click.Context, follow: bool, lines: int) -> None:
    """View orchestrator logs (supports both foreground and background modes)."""
    import subprocess  # noqa: PLC0415

    config = ctx.obj["config"]
    project_dir = Path.cwd()

    # Check for foreground log first (orchestration.log in current dir)
    foreground_log = project_dir / "orchestration.log"
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
        click.echo("  - Foreground: 'rasen run' (creates orchestration.log)")
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
