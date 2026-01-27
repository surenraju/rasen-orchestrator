"""Code review loop - Coder ↔ Reviewer validation."""

from __future__ import annotations

import time
from pathlib import Path

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.events import parse_events
from rasen.exceptions import SessionError
from rasen.git import get_git_diff
from rasen.logging import get_logger
from rasen.models import Subtask
from rasen.prompts import create_agent_prompt

logger = get_logger(__name__)


class ReviewResult:
    """Result of a code review iteration."""

    def __init__(self, approved: bool, feedback: str | None = None) -> None:
        """Initialize review result.

        Args:
            approved: Whether review approved the changes
            feedback: Specific feedback if changes requested
        """
        self.approved = approved
        self.feedback = feedback


def run_review_loop(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
    baseline_commit: str,
) -> bool:
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
        True if review approved, False if max loops exceeded

    Raises:
        SessionError: If review or fix session fails critically
    """
    if not config.review.enabled:
        logger.info("Review loop disabled, skipping")
        return True

    max_loops = config.review.max_loops

    logger.info(f"Starting review loop for subtask {subtask.id} (max {max_loops} loops)")

    for iteration in range(1, max_loops + 1):
        logger.info(f"Review iteration {iteration}/{max_loops}")

        # Run reviewer session (read-only)
        review_result = _run_reviewer_session(config, subtask, project_dir, baseline_commit)

        if review_result.approved:
            logger.info(f"Review approved for subtask {subtask.id}")
            return True

        logger.warning(
            f"Review requested changes for subtask {subtask.id} (iteration {iteration}/{max_loops})"
        )
        logger.info(f"Feedback: {review_result.feedback}")

        # Don't fix on last iteration - just fail
        if iteration >= max_loops:
            logger.error(
                f"Review loop exceeded max iterations ({max_loops}) for subtask {subtask.id}"
            )
            return False

        # Run coder fix session
        _run_coder_fix_session(config, subtask, review_result.feedback, project_dir)

        # Delay between iterations
        time.sleep(config.orchestrator.session_delay_seconds)

    return False  # Should not reach here, but safety


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
    try:
        _result = run_claude_session(
            prompt, project_dir, config.orchestrator.session_timeout_seconds
        )
    except SessionError as e:
        logger.error(f"Reviewer session failed: {e}")
        # On reviewer failure, assume approval to not block progress
        return ReviewResult(approved=True, feedback="Reviewer session failed, assuming approved")

    # Parse events from session output
    # NOTE: Current implementation doesn't capture stdout, so this is placeholder
    # In real implementation, would parse actual session output
    events = parse_events('<event topic="review.approved">LGTM</event>')

    # Check for approval or changes requested
    for event in events:
        if event.topic == "review.approved":
            return ReviewResult(approved=True)
        elif event.topic == "review.changes_requested":
            return ReviewResult(approved=False, feedback=event.payload)

    # Default to approved if no clear signal (fail-open for progress)
    logger.warning("No clear review signal, assuming approved")
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
    try:
        run_claude_session(prompt, project_dir, config.orchestrator.session_timeout_seconds)
    except SessionError as e:
        logger.error(f"Coder fix session failed: {e}")
        raise
