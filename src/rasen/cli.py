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
    """Initialize a new task."""
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
    click.echo(f"   Task description saved to: {task_file}\n   State directory: {rasen_dir}\n")
    click.echo("Run 'rasen run' to start the orchestration loop")


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
    log_file = Path(config.background.log_file)

    # Check if already running
    from rasen.daemon import get_daemon_status  # noqa: PLC0415

    status = get_daemon_status(pid_file)
    if status["running"]:
        click.echo(f"Daemon already running with PID {status['pid']}")
        click.echo("Use 'rasen stop' to stop it first, or 'rasen status' to check progress")
        return

    # Setup logging
    setup_logging(log_file if background else None)

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
    """Show current status."""
    from rasen.stores.status_store import StatusStore  # noqa: PLC0415

    config = ctx.obj["config"]
    status_file = Path(config.background.status_file)

    store = StatusStore(status_file)
    status = store.load()

    if not status:
        click.echo("Status: Not running")
        return

    click.echo(f"Status: {status.status}")
    click.echo(f"PID: {status.pid}")
    click.echo(f"Iteration: {status.iteration}")
    click.echo(f"Progress: {status.completed_subtasks}/{status.total_subtasks} subtasks")
    click.echo(f"Total commits: {status.total_commits}")
    if status.subtask_id:
        click.echo(f"Current subtask: {status.subtask_id}")
        click.echo(f"  {status.subtask_description}")
    click.echo(f"Last activity: {status.last_activity}")


@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", default=50, help="Number of lines to show")
@click.pass_context
def logs(ctx: click.Context, follow: bool, lines: int) -> None:
    """View orchestrator logs."""
    import subprocess  # noqa: PLC0415

    config = ctx.obj["config"]
    log_file = Path(config.background.log_file)

    if not log_file.exists():
        click.echo("No log file found. Daemon may not have been started yet.")
        return

    if follow:
        click.echo(f"Following log file: {log_file} (Ctrl+C to stop)")
        click.echo("---")
        try:
            # Use tail -f to follow log
            subprocess.run(["tail", "-f", str(log_file)], check=False)
        except KeyboardInterrupt:
            click.echo("\nStopped following log")
    else:
        # Show last N lines
        try:
            result = subprocess.run(
                ["tail", "-n", str(lines), str(log_file)],
                capture_output=True,
                text=True,
                check=True,
            )
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
