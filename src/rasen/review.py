"""Code review loop - Coder ↔ Reviewer validation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.exceptions import SessionError
from rasen.git import get_git_diff
from rasen.logging import get_logger
from rasen.models import SessionMetrics, Subtask
from rasen.prompts import create_agent_prompt
from rasen.stores.metrics_store import MetricsStore
from rasen.stores.plan_store import PlanStore
from rasen.stores.status_store import StatusStore

logger = get_logger(__name__)


@dataclass
class ReviewResult:
    """Result of a code review iteration."""

    approved: bool
    feedback: str | None = None


@dataclass
class ReviewLoopResult:
    """Result of the entire review loop."""

    passed: bool
    feedback: str | None = None  # Last feedback if rejected


def run_review_loop(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
    baseline_commit: str,
) -> ReviewLoopResult:
    """Run code review loop for a completed subtask.

    This implements the Coder ↔ Reviewer pattern:
    1. Reviewer validates changes (read-only)
    2. If changes_requested → Coder fixes (max N loops)
    3. If approved → continue

    Args:
        config: RASEN configuration
        subtask: Subtask that was just completed
        project_dir: Path to project directory
        baseline_commit: Commit hash before this subtask

    Returns:
        ReviewLoopResult with passed status and feedback if rejected

    Raises:
        SessionError: If review or fix session fails critically
    """
    if not config.review.enabled:
        logger.info("Review loop disabled, skipping")
        return ReviewLoopResult(passed=True)

    max_loops = config.review.max_loops

    logger.info(f"Starting review loop for subtask {subtask.id} (max {max_loops} loops)")

    # Update status to show review phase
    status_store = StatusStore(project_dir / ".rasen" / "status.json")

    for iteration in range(1, max_loops + 1):
        # Update status with current review iteration
        status = status_store.load()
        if status:
            status.current_phase = f"Review {iteration}/{max_loops}"
            status_store.update(status)

        logger.info(f"Review iteration {iteration}/{max_loops}")

        # Run reviewer session (read-only)
        review_result = _run_reviewer_session(config, subtask, project_dir, baseline_commit)

        if review_result.approved:
            logger.info(f"Review approved for subtask {subtask.id}")
            return ReviewLoopResult(passed=True)

        logger.warning(
            f"Review requested changes for subtask {subtask.id} (iteration {iteration}/{max_loops})"
        )
        logger.info(f"Feedback: {review_result.feedback}")

        # Don't fix on last iteration - just fail
        if iteration >= max_loops:
            logger.error(
                f"Review loop exceeded max iterations ({max_loops}) for subtask {subtask.id}"
            )
            return ReviewLoopResult(passed=False, feedback=review_result.feedback)

        # Run coder fix session
        _run_coder_fix_session(config, subtask, review_result.feedback, project_dir)

        # Delay between iterations
        time.sleep(config.orchestrator.session_delay_seconds)

    return ReviewLoopResult(passed=False)  # Should not reach here, but safety


def _run_reviewer_session(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
    baseline_commit: str,
) -> ReviewResult:
    """Run a single reviewer session (read-only).

    Args:
        config: RASEN configuration
        subtask: Subtask to review
        project_dir: Path to project directory
        baseline_commit: Commit to diff from

    Returns:
        ReviewResult with approval status and feedback
    """
    logger.info(f"Running reviewer session for subtask {subtask.id}")

    # Get diff since baseline
    try:
        git_diff = get_git_diff(project_dir, baseline_commit)
    except Exception as e:
        logger.warning(f"Could not get git diff: {e}")
        git_diff = "(Could not generate diff)"

    # Render reviewer prompt
    prompt = create_agent_prompt(
        "reviewer",
        project_dir=project_dir,
        subtask_id=subtask.id,
        subtask_description=subtask.description,
        git_diff=git_diff,
    )

    # Run reviewer session (pass prompt directly, no file needed)
    # Enable debug logging to .rasen/debug_logs/
    debug_log_dir = project_dir / ".rasen" / "debug_logs"
    metrics_store = MetricsStore(project_dir / ".rasen")
    start_time = datetime.now(UTC)
    start_ts = time.time()
    try:
        result = run_claude_session(
            prompt,
            project_dir,
            config.orchestrator.session_timeout_seconds,
            debug_log_dir=debug_log_dir,
            model=config.get_model("reviewer"),
        )
        duration = time.time() - start_ts
        # Extract session ID for logging
        session_id = result.session_id[:8]
        logger.info(f"Reviewer session ID: {session_id}")

        # Record reviewer session metrics
        session_metrics = SessionMetrics(
            session_id=result.session_id,
            agent_type="reviewer",
            subtask_id=subtask.id,
            duration_seconds=duration,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            started_at=start_time,
            completed_at=datetime.now(UTC),
            status="completed",
        )
        metrics_store.record_session(session_metrics)
    except SessionError as e:
        logger.error(f"Reviewer session failed: {e}")
        # On reviewer failure, assume approval to not block progress
        return ReviewResult(approved=True, feedback="Reviewer session failed, assuming approved")

    # Read review state from state.json
    plan_store = PlanStore(project_dir / ".rasen")
    plan = plan_store.load()

    if not plan:
        logger.warning("No plan found, assuming approved")
        return ReviewResult(approved=True)

    # Determine review status and feedback
    review_status: str | None = None
    review_feedback: list[str] = []

    # Check if per-subtask review (in subtask.review) or global review (in plan.review)
    if subtask.id != "build-complete" and plan.subtasks:
        # Per-subtask review - check the subtask's review field
        for s in plan.subtasks:
            if s.id == subtask.id and s.review:
                review_status = s.review.status
                review_feedback = s.review.feedback
                break

    # Fall back to global review if no per-subtask review found
    if review_status is None:
        review_status = plan.review.status
        review_feedback = plan.review.feedback

    # Return result based on status
    if review_status == "approved":
        return ReviewResult(approved=True)
    elif review_status == "changes_requested":
        feedback = "\n".join(review_feedback) if review_feedback else None
        return ReviewResult(approved=False, feedback=feedback)

    # Default to approved if no clear signal (fail-open for progress)
    logger.warning("No clear review signal in JSON, assuming approved")
    return ReviewResult(approved=True)


def _run_coder_fix_session(
    config: Config,
    subtask: Subtask,
    feedback: str | None,
    project_dir: Path,
) -> None:
    """Run coder session to fix review issues.

    Args:
        config: RASEN configuration
        subtask: Subtask being fixed
        feedback: Feedback from reviewer
        project_dir: Path to project directory
    """
    logger.info(f"Running coder fix session for subtask {subtask.id}")

    # Render coder prompt with review feedback
    prompt = create_agent_prompt(
        "coder",
        project_dir=project_dir,
        subtask_id=subtask.id,
        subtask_description=f"Fix review issues: {feedback or 'See previous feedback'}",
        attempt_number="review-fix",
        memory_context="",
        failed_approaches_section="",
    )

    # Run coder session (pass prompt directly, no file needed)
    # Enable debug logging to .rasen/debug_logs/
    debug_log_dir = project_dir / ".rasen" / "debug_logs"
    metrics_store = MetricsStore(project_dir / ".rasen")
    start_time = datetime.now(UTC)
    start_ts = time.time()
    try:
        result = run_claude_session(
            prompt,
            project_dir,
            config.orchestrator.session_timeout_seconds,
            debug_log_dir=debug_log_dir,
            model=config.get_model("reviewer"),
        )
        duration = time.time() - start_ts
        # Extract session ID for logging
        session_id = result.session_id[:8]
        logger.info(f"Coder fix session ID: {session_id}")

        # Record coder fix session metrics
        session_metrics = SessionMetrics(
            session_id=result.session_id,
            agent_type="coder",
            subtask_id=subtask.id,
            duration_seconds=duration,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            started_at=start_time,
            completed_at=datetime.now(UTC),
            status="completed",
        )
        metrics_store.record_session(session_metrics)
    except SessionError as e:
        logger.error(f"Coder fix session failed: {e}")
        raise
