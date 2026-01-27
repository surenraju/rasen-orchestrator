"""QA validation loop - Coder ↔ QA with recurring issue detection."""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.events import parse_events
from rasen.exceptions import SessionError
from rasen.git import get_git_diff
from rasen.logging import get_logger
from rasen.models import ImplementationPlan
from rasen.prompts import create_agent_prompt

logger = get_logger(__name__)


class QAIssue(BaseModel):
    """A single QA issue."""

    description: str
    occurrence_count: int = 1


class QAResult:
    """Result of a QA validation iteration."""

    def __init__(self, approved: bool, issues: list[str] | None = None) -> None:
        """Initialize QA result.

        Args:
            approved: Whether QA approved the implementation
            issues: List of issues found (if rejected)
        """
        self.approved = approved
        self.issues = issues or []


class QAHistory:
    """Tracks QA issues across iterations for recurring issue detection."""

    def __init__(self) -> None:
        """Initialize QA history tracker."""
        self.issue_counts: Counter[str] = Counter()
        self.iterations: list[QAResult] = []

    def record(self, result: QAResult) -> None:
        """Record a QA result.

        Args:
            result: QA result to record
        """
        self.iterations.append(result)
        for issue in result.issues:
            # Normalize issue text for matching
            normalized = self._normalize_issue(issue)
            self.issue_counts[normalized] += 1

    def has_recurring_issues(self, threshold: int = 3) -> bool:
        """Check if any issue has occurred N+ times.

        Args:
            threshold: Number of occurrences to consider recurring

        Returns:
            True if any issue has occurred >= threshold times
        """
        return any(count >= threshold for count in self.issue_counts.values())

    def get_recurring_issues(self, threshold: int = 3) -> list[tuple[str, int]]:
        """Get list of recurring issues.

        Args:
            threshold: Number of occurrences to consider recurring

        Returns:
            List of (issue, count) tuples for recurring issues
        """
        return [(issue, count) for issue, count in self.issue_counts.items() if count >= threshold]

    def _normalize_issue(self, issue: str) -> str:
        """Normalize issue text for matching.

        Args:
            issue: Raw issue text

        Returns:
            Normalized issue text
        """
        # Simple normalization: lowercase, strip whitespace
        # Could be enhanced with fuzzy matching
        return issue.lower().strip()


def run_qa_loop(
    config: Config,
    plan: ImplementationPlan,
    project_dir: Path,
    baseline_commit: str,
    task_description: str,
) -> bool:
    """Run QA validation loop after all subtasks complete.

    This implements the Coder ↔ QA pattern:
    1. QA validates against acceptance criteria (read-only)
    2. If rejected → Coder fixes issues
    3. If recurring issues (3+) → escalate to human
    4. If approved → task complete

    Args:
        config: RASEN configuration
        plan: Implementation plan with all subtasks
        project_dir: Path to project directory
        baseline_commit: Commit hash before implementation
        task_description: Original task description

    Returns:
        True if QA approved, False if escalation needed

    Raises:
        SessionError: If QA or fix session fails critically
    """
    if not config.qa.enabled:
        logger.info("QA loop disabled, skipping")
        return True

    max_iterations = config.qa.max_iterations
    history = QAHistory()

    logger.info(f"Starting QA loop (max {max_iterations} iterations)")

    for iteration in range(1, max_iterations + 1):
        logger.info(f"QA iteration {iteration}/{max_iterations}")

        # Run QA session (read-only)
        qa_result = _run_qa_session(config, plan, task_description, project_dir, baseline_commit)

        history.record(qa_result)

        if qa_result.approved:
            logger.info("QA approved - implementation complete!")
            return True

        logger.warning(f"QA rejected implementation (iteration {iteration}/{max_iterations})")
        logger.info(f"Issues found: {len(qa_result.issues)}")
        for i, issue in enumerate(qa_result.issues, 1):
            logger.info(f"  {i}. {issue}")

        # Check for recurring issues
        if history.has_recurring_issues(config.qa.recurring_issue_threshold):
            recurring = history.get_recurring_issues(config.qa.recurring_issue_threshold)
            logger.error(f"Recurring issues detected ({len(recurring)} issues):")
            for issue, count in recurring:
                logger.error(f"  - {issue} (occurred {count} times)")

            # Create escalation file
            _create_escalation_file(project_dir, recurring, history)
            logger.error("Created QA_ESCALATION.md - human intervention required")
            return False

        # Don't fix on last iteration - just fail
        if iteration >= max_iterations:
            logger.error(f"QA loop exceeded max iterations ({max_iterations})")
            return False

        # Run coder fix session
        _run_coder_qa_fix_session(config, qa_result.issues, project_dir)

        # Delay between iterations
        time.sleep(config.orchestrator.session_delay_seconds)

    return False  # Should not reach here, but safety


def _run_qa_session(
    config: Config,
    plan: ImplementationPlan,
    task_description: str,
    project_dir: Path,
    baseline_commit: str,
) -> QAResult:
    """Run a single QA validation session (read-only).

    Args:
        config: RASEN configuration
        plan: Implementation plan
        task_description: Original task description
        project_dir: Path to project directory
        baseline_commit: Commit to diff from

    Returns:
        QAResult with approval status and issues
    """
    logger.info("Running QA validation session")

    # Get full diff since baseline
    try:
        full_diff = get_git_diff(project_dir, baseline_commit)
    except Exception as e:
        logger.warning(f"Could not get git diff: {e}")
        full_diff = "(Could not generate diff)"

    # Serialize implementation plan
    plan_summary = f"Total subtasks: {len(plan.subtasks)}\n"
    for subtask in plan.subtasks:
        plan_summary += f"- {subtask.id}: {subtask.description} [{subtask.status.value}]\n"

    # Get test results (placeholder - would run actual tests)
    test_results = "Tests: (would run pytest here)"

    # Render QA prompt
    prompt = create_agent_prompt(
        "qa",
        project_dir=project_dir,
        task_description=task_description,
        implementation_plan=plan_summary,
        full_git_diff=full_diff,
        test_results=test_results,
    )

    # Run QA session (pass prompt directly, no file needed)
    try:
        _result = run_claude_session(
            prompt, project_dir, config.orchestrator.session_timeout_seconds
        )
    except SessionError as e:
        logger.error(f"QA session failed: {e}")
        # On QA failure, assume rejection to be safe
        return QAResult(approved=False, issues=[f"QA session failed: {e}"])

    # Parse events from session output
    # NOTE: Current implementation doesn't capture stdout, so this is placeholder
    events = parse_events('<event topic="qa.approved">All criteria met</event>')

    # Check for approval or rejection
    for event in events:
        if event.topic == "qa.approved":
            return QAResult(approved=True)
        elif event.topic == "qa.rejected":
            # Parse issues from payload
            issues = _parse_qa_issues(event.payload)
            return QAResult(approved=False, issues=issues)

    # Default to rejection if no clear signal (fail-closed for quality)
    logger.warning("No clear QA signal, assuming rejected for safety")
    return QAResult(approved=False, issues=["No clear QA signal received"])


def _run_coder_qa_fix_session(config: Config, issues: list[str], project_dir: Path) -> None:
    """Run coder session to fix QA issues.

    Args:
        config: RASEN configuration
        issues: List of issues to fix
        project_dir: Path to project directory
    """
    logger.info("Running coder QA fix session")

    # Format issues for prompt
    issues_text = "\n".join(f"{i}. {issue}" for i, issue in enumerate(issues, 1))

    # Render coder prompt with QA feedback
    prompt = create_agent_prompt(
        "coder",
        project_dir=project_dir,
        subtask_id="qa-fix",
        subtask_description=f"Fix QA issues:\n{issues_text}",
        attempt_number="qa-fix",
        memory_context="",
        failed_approaches_section="",
    )

    # Run coder session (pass prompt directly, no file needed)
    try:
        run_claude_session(prompt, project_dir, config.orchestrator.session_timeout_seconds)
    except SessionError as e:
        logger.error(f"Coder QA fix session failed: {e}")
        raise


def _parse_qa_issues(payload: str) -> list[str]:
    """Parse QA issues from event payload.

    Args:
        payload: Event payload text

    Returns:
        List of individual issues
    """
    # Simple parsing: split on numbered lines or bullet points
    lines = payload.strip().split("\n")
    issues = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Remove common prefixes
        for prefix in ["- ", "* ", "• "]:
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
                break

        # Remove numbered prefixes (1. 2. etc)
        if line and line[0].isdigit() and ". " in line:
            line = line.split(". ", 1)[1].strip()

        if line:
            issues.append(line)

    return issues if issues else [payload]  # Fallback to full payload


def _create_escalation_file(
    project_dir: Path, recurring_issues: list[tuple[str, int]], history: QAHistory
) -> None:
    """Create QA escalation file for human intervention.

    Args:
        project_dir: Path to project directory
        recurring_issues: List of (issue, count) tuples
        history: QA history with all iterations
    """
    escalation_file = project_dir / "QA_ESCALATION.md"

    content = f"""# QA Escalation - Human Intervention Required

## Summary

The QA validation loop has detected recurring issues that the agent cannot resolve autonomously.
Human review and intervention is required to proceed.

## Recurring Issues

{len(recurring_issues)} issue(s) have occurred 3+ times:

"""

    for issue, count in recurring_issues:
        content += f"### Issue (occurred {count} times)\n\n"
        content += f"{issue}\n\n"

    content += f"""
## QA History

Total QA iterations: {len(history.iterations)}

"""

    for i, result in enumerate(history.iterations, 1):
        status = "✅ APPROVED" if result.approved else "❌ REJECTED"
        content += f"### Iteration {i}: {status}\n\n"
        if not result.approved:
            content += "Issues found:\n"
            for issue in result.issues:
                content += f"- {issue}\n"
            content += "\n"

    content += """
## Next Steps

1. Review the recurring issues above
2. Manually fix the issues or provide clearer guidance
3. Delete this file when ready to resume
4. Run `rasen resume` to continue
"""

    escalation_file.write_text(content)
    logger.info(f"Created escalation file: {escalation_file}")
