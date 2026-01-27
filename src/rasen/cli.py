"""RASEN CLI - Command line interface."""

from __future__ import annotations

import click

from rasen import __version__
from rasen.config import load_config


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
def init(ctx: click.Context, task: str) -> None:  # noqa: ARG001
    """Initialize a new task."""
    click.echo(f"Initializing task: {task}")
    # Implementation in later task


@main.command()
@click.option("--background", is_flag=True, help="Run in background")
@click.option("--skip-review", is_flag=True, help="Skip Coder ↔ Reviewer loop")
@click.option("--skip-qa", is_flag=True, help="Skip Coder ↔ QA loop")
@click.pass_context
def run(ctx: click.Context, background: bool, skip_review: bool, skip_qa: bool) -> None:
    """Run the orchestration loop."""
    config = ctx.obj["config"]
    # Override config with CLI flags
    if skip_review:
        config.review.enabled = False
    if skip_qa:
        config.qa.enabled = False
    msg = (
        f"Running orchestrator (background={background}, "
        f"review={config.review.enabled}, qa={config.qa.enabled})"
    )
    click.echo(msg)
    # Implementation in later task


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:  # noqa: ARG001
    """Show current status."""
    click.echo("Status: Not running")
    # Implementation in later task


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
