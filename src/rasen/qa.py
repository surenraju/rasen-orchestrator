"""QA validation loop - Coder ↔ QA with recurring issue detection."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.exceptions import SessionError
from rasen.git import get_git_diff
from rasen.logging import get_logger
from rasen.models import ImplementationPlan, SessionMetrics, Subtask
from rasen.prompts import create_agent_prompt
from rasen.stores.metrics_store import MetricsStore
from rasen.stores.plan_store import PlanStore
from rasen.stores.status_store import StatusStore

logger = get_logger(__name__)


@dataclass
class QAResult:
    """Result of a QA validation iteration."""

    approved: bool
    issues: list[str] = field(default_factory=list)


class QALoopResult(BaseModel):
    """Result of the entire QA loop."""

    passed: bool
    issues: list[str] = []  # Issues if rejected


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


def run_qa_for_subtask(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
    baseline_commit: str,
) -> QALoopResult:
    """Run QA validation for a single completed subtask.

    This is a lighter-weight QA check for per-subtask validation.
    It checks:
    1. Acceptance criteria are met
    2. Required test files exist
    3. Tests pass

    Args:
        config: RASEN configuration
        subtask: Subtask that was just completed
        project_dir: Path to project directory
        baseline_commit: Commit before subtask started

    Returns:
        QALoopResult with passed status and issues if rejected
    """

    if not config.qa.enabled:
        logger.info("QA disabled, skipping per-subtask QA")
        return QALoopResult(passed=True)

    logger.info(f"Running per-subtask QA for subtask {subtask.id}")

    # Get diff for just this subtask
    try:
        diff = get_git_diff(project_dir, baseline_commit)
    except Exception as e:
        logger.warning(f"Could not get git diff: {e}")
        diff = "(Could not generate diff)"

    # Build QA context for subtask
    subtask_context = f"""
## Subtask {subtask.id}: {subtask.title or subtask.description[:50]}

**Description:**
{subtask.description}

**Acceptance Criteria:**
{chr(10).join(f'- {c}' for c in (subtask.acceptance_criteria or []))}

**Expected Files:**
{chr(10).join(f'- {f}' for f in (subtask.files or []))}

**Expected Tests:**
{chr(10).join(f'- {t}' for t in (subtask.tests or []))}
"""

    # Render QA prompt for subtask
    prompt = create_agent_prompt(
        "qa",
        project_dir=project_dir,
        task_description=subtask_context,
        implementation_plan=f"Validating subtask {subtask.id}",
        full_git_diff=diff,
        test_results="(run tests for this subtask)",
    )

    # Run QA session
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
        )
        duration = time.time() - start_ts
        session_id = result.session_id[:8]
        logger.info(f"Per-subtask QA session ID: {session_id}")

        # Record metrics
        session_metrics = SessionMetrics(
            session_id=result.session_id,
            agent_type="qa",
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
        logger.error(f"Per-subtask QA session failed: {e}")
        return QALoopResult(passed=False, issues=[f"QA session failed: {e}"])

    # Check QA result from state.json
    plan_store = PlanStore(project_dir / ".rasen")
    updated_plan = plan_store.load()

    # Determine qa_result based on plan/subtask qa status
    qa_result = QALoopResult(passed=True)  # Default to pass for per-subtask

    if not updated_plan:
        logger.warning("No plan found after QA, assuming rejected")
        qa_result = QALoopResult(passed=False, issues=["No plan found"])
    else:
        # Find the subtask and check its qa field
        subtask_qa_found = False
        for s in updated_plan.subtasks:
            if s.id == subtask.id and s.qa:
                subtask_qa_found = True
                qa_status = s.qa.status if hasattr(s.qa, "status") else None
                qa_issues = s.qa.issues if hasattr(s.qa, "issues") else []
                if qa_status == "approved":
                    logger.info(f"Per-subtask QA approved for {subtask.id}")
                    qa_result = QALoopResult(passed=True)
                elif qa_status == "rejected":
                    logger.warning(f"Per-subtask QA rejected for {subtask.id}")
                    qa_result = QALoopResult(passed=False, issues=qa_issues or ["No details"])
                break

        # Check plan-level QA as fallback if no subtask-level qa
        if not subtask_qa_found:
            if updated_plan.qa.status == "approved":
                qa_result = QALoopResult(passed=True)
            elif updated_plan.qa.status == "rejected":
                qa_result = QALoopResult(passed=False, issues=updated_plan.qa.issues)
            else:
                logger.info(f"No clear QA signal for {subtask.id}, defaulting to passed")

    return qa_result


def run_qa_loop(
    config: Config,
    plan: ImplementationPlan,
    project_dir: Path,
    baseline_commit: str,
    task_description: str,
) -> QALoopResult:
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
        QALoopResult with passed status and issues if rejected

    Raises:
        SessionError: If QA or fix session fails critically
    """
    if not config.qa.enabled:
        logger.info("QA loop disabled, skipping")
        return QALoopResult(passed=True)

    max_iterations = config.qa.max_iterations
    history = QAHistory()

    logger.info(f"Starting QA loop (max {max_iterations} iterations)")

    # Update status to show QA phase
    status_store = StatusStore(project_dir / ".rasen" / "status.json")

    for iteration in range(1, max_iterations + 1):
        # Update status with current QA iteration
        status = status_store.load()
        if status:
            status.current_phase = f"QA {iteration}/{max_iterations}"
            status_store.update(status)

        logger.info(f"QA iteration {iteration}/{max_iterations}")

        # Run QA session (read-only)
        qa_result = _run_qa_session(config, plan, task_description, project_dir, baseline_commit)

        history.record(qa_result)

        if qa_result.approved:
            logger.info("QA approved - implementation complete!")
            return QALoopResult(passed=True)

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
            recurring_issues = [f"{issue} (x{count})" for issue, count in recurring]
            return QALoopResult(passed=False, issues=recurring_issues)

        # Don't fix on last iteration - just fail
        if iteration >= max_iterations:
            logger.error(f"QA loop exceeded max iterations ({max_iterations})")
            return QALoopResult(passed=False, issues=qa_result.issues)

        # Run coder fix session
        _run_coder_qa_fix_session(config, qa_result.issues, project_dir)

        # Delay between iterations
        time.sleep(config.orchestrator.session_delay_seconds)

    return QALoopResult(passed=False)  # Should not reach here, but safety


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
        )
        duration = time.time() - start_ts
        # Extract session ID for logging
        session_id = result.session_id[:8]
        logger.info(f"QA session ID: {session_id}")

        # Record QA session metrics
        session_metrics = SessionMetrics(
            session_id=result.session_id,
            agent_type="qa",
            subtask_id=None,
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
        logger.error(f"QA session failed: {e}")
        # On QA failure, assume rejection to be safe
        return QAResult(approved=False, issues=[f"QA session failed: {e}"])

    # Read QA state from state.json
    plan_store = PlanStore(project_dir / ".rasen")
    updated_plan = plan_store.load()

    if not updated_plan:
        logger.warning("No plan found, assuming rejected for safety")
        return QAResult(approved=False, issues=["No implementation plan found"])

    if updated_plan.qa.status == "approved":
        return QAResult(approved=True)
    elif updated_plan.qa.status == "rejected":
        return QAResult(approved=False, issues=updated_plan.qa.issues)

    # Default to rejection if no clear signal (fail-closed for quality)
    logger.warning("No clear QA signal in JSON, assuming rejected for safety")
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
        )
        duration = time.time() - start_ts
        # Extract session ID for logging
        session_id = result.session_id[:8]
        logger.info(f"Coder QA fix session ID: {session_id}")

        # Record coder QA fix session metrics
        session_metrics = SessionMetrics(
            session_id=result.session_id,
            agent_type="coder",
            subtask_id="qa-fix",
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
        logger.error(f"Coder QA fix session failed: {e}")
        raise


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
