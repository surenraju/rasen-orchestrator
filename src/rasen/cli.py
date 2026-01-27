"""RASEN CLI - Command line interface."""

from __future__ import annotations

from pathlib import Path

import click

from rasen import __version__
from rasen.config import load_config
from rasen.logging import setup_logging


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

    # TODO: Run initializer agent session
    # For now, just create placeholder
    rasen_dir = Path(config.project.root) / ".rasen"
    rasen_dir.mkdir(parents=True, exist_ok=True)

    click.echo("\n✅ Task initialized")
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

    # Setup logging
    log_file = Path(config.background.log_file) if background else None
    setup_logging(log_file)

    msg = (
        f"Running orchestrator (background={background}, "
        f"review={config.review.enabled}, qa={config.qa.enabled})"
    )
    click.echo(msg)

    # TODO: Handle background mode properly
    if background:
        click.echo("Background mode not yet implemented")
        return

    # Run orchestration loop
    project_dir = Path(config.project.root)
    loop = OrchestrationLoop(config, project_dir)

    try:
        reason = loop.run()
        click.echo(f"\nOrchestration completed: {reason.value}")
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user")
    except Exception as e:
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
@click.pass_context
def logs(ctx: click.Context, follow: bool) -> None:  # noqa: ARG001
    """View orchestrator logs."""
    click.echo("Logs not available")
    # Implementation in later task


@main.command()
@click.pass_context
def stop(ctx: click.Context) -> None:  # noqa: ARG001
    """Stop background orchestrator."""
    click.echo("Stop command")
    # Implementation in later task


@main.command()
@click.pass_context
def resume(ctx: click.Context) -> None:  # noqa: ARG001
    """Resume after interruption."""
    click.echo("Resume command")
    # Implementation in later task


@main.command()
@click.pass_context
def merge(ctx: click.Context) -> None:  # noqa: ARG001
    """Merge completed worktree."""
    click.echo("Merge command")
    # Implementation in later task


if __name__ == "__main__":
    main()
