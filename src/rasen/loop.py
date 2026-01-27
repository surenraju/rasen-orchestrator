"""Main orchestration loop for RASEN."""

from __future__ import annotations

import os
import time
from pathlib import Path

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.daemon import should_shutdown
from rasen.events import has_blocked_event, has_completion_event, parse_events
from rasen.exceptions import SessionError, StallDetectedError
from rasen.git import count_new_commits, get_current_commit, is_git_repo
from rasen.logging import get_logger
from rasen.models import (
    LoopState,
    SessionResult,
    SessionStatus,
    Subtask,
    SubtaskStatus,
    TerminationReason,
)
from rasen.prompts import create_agent_prompt
from rasen.qa import run_qa_loop
from rasen.review import run_review_loop
from rasen.stores.memory_store import MemoryStore
from rasen.stores.plan_store import PlanStore
from rasen.stores.recovery_store import RecoveryStore
from rasen.stores.status_store import StatusInfo, StatusStore
from rasen.validation import validate_completion

logger = get_logger(__name__)


class OrchestrationLoop:
    """Main orchestration loop that manages agent sessions."""

    def __init__(self, config: Config, project_dir: Path, task_description: str = "") -> None:
        """Initialize orchestration loop.

        Args:
            config: RASEN configuration
            project_dir: Path to project directory
            task_description: Original task description (for QA)
        """
        self.config = config
        self.project_dir = project_dir
        self.rasen_dir = project_dir / ".rasen"
        self.task_description = task_description

        # Initialize stores
        self.plan_store = PlanStore(self.rasen_dir)
        self.recovery_store = RecoveryStore(self.rasen_dir)
        self.memory_store = MemoryStore(Path(config.memory.path))
        self.status_store = StatusStore(Path(config.background.status_file))

        # State
        self.state = LoopState()
        self.no_commit_counts: dict[str, int] = {}
        self.baseline_commit = self._get_commit_hash()  # Capture at start

    def run(self) -> TerminationReason:  # noqa: PLR0911
        """Run the orchestration loop until completion or termination.

        Returns:
            Reason for termination
        """
        logger.info("Starting orchestration loop")

        try:
            # Main loop
            while self.state.iteration < self.config.orchestrator.max_iterations:
                # Check for shutdown request
                if should_shutdown():
                    logger.info("Shutdown requested, saving state and exiting gracefully")
                    self.status_store.update(
                        StatusInfo(
                            pid=os.getpid(),
                            iteration=self.state.iteration,
                            subtask_id=self.state.current_subtask_id or "",
                            subtask_description="",
                            status="interrupted",
                            total_commits=self.state.total_commits,
                            completed_subtasks=self.plan_store.get_completion_stats()[0],
                            total_subtasks=self.plan_store.get_completion_stats()[1],
                        )
                    )
                    return TerminationReason.USER_CANCELLED

                self.state.iteration += 1

                # Session 1: Check if plan exists, if not run Initializer
                plan = self.plan_store.load()
                if not plan:
                    logger.info(
                        f"No plan found, running Initializer (Session {self.state.iteration})"
                    )

                    if not self.task_description:
                        logger.error("No task description provided for initialization")
                        self.status_store.mark_failed("No task description")
                        return TerminationReason.ERROR

                    # Run Initializer agent to create plan
                    try:
                        session_result = self._run_initializer_session(self.task_description)

                        # Reload plan after Initializer runs
                        plan = self.plan_store.load()
                        if not plan:
                            logger.error("Initializer failed to create implementation plan")
                            self.status_store.mark_failed("Plan creation failed")
                            return TerminationReason.ERROR

                        logger.info(
                            f"Session {self.state.iteration}: "
                            f"Plan created with {len(plan.subtasks)} subtasks"
                        )

                        # Delay before starting subtasks
                        time.sleep(self.config.orchestrator.session_delay_seconds)

                    except SessionError as e:
                        logger.error(f"Initializer session failed: {e}")
                        self.status_store.mark_failed("Initializer failed")
                        return TerminationReason.ERROR

                # Get next subtask
                subtask = self.plan_store.get_next_subtask()
                if not subtask:
                    # All subtasks complete - run validation
                    logger.info("All subtasks complete")
                    plan = self.plan_store.load()
                    baseline_commit = self._get_commit_hash()

                    # Run Review loop if enabled and NOT per-subtask
                    if self.config.review.enabled and not self.config.review.per_subtask:
                        logger.info("Running Review validation for entire build")
                        build_subtask = Subtask(
                            id="build-complete",
                            description="Complete build review",
                            status=SubtaskStatus.COMPLETED,
                        )
                        review_passed = run_review_loop(
                            self.config, build_subtask, self.project_dir, baseline_commit
                        )
                        if not review_passed:
                            logger.error("Build-wide review failed")
                            self.status_store.mark_failed("Review validation failed")
                            return TerminationReason.ERROR

                    # Run QA loop if enabled
                    if plan and self.config.qa.enabled:
                        logger.info("Running QA validation for entire build")
                        qa_passed = run_qa_loop(
                            self.config,
                            plan,
                            self.project_dir,
                            baseline_commit,
                            self.task_description,
                        )

                        if not qa_passed:
                            logger.error("QA validation failed or escalated")
                            self.status_store.mark_failed("QA validation failed")
                            return TerminationReason.ERROR

                    # All done!
                    logger.info("All validation complete - task finished!")
                    self.status_store.mark_completed()
                    return TerminationReason.COMPLETE

                # Update status
                self._update_status(subtask.id, subtask.description, "running")

                # Mark subtask as in progress
                self.plan_store.mark_in_progress(subtask.id)
                self.state.current_subtask_id = subtask.id

                # Run session for this subtask
                logger.info(f"Session {self.state.iteration}: Working on {subtask.id}")
                commit_before = self._get_commit_hash()

                try:
                    session_result = self._run_session(subtask.id, subtask.description)

                    # Post-session processing
                    commits_made = self._count_commits_since(commit_before)
                    session_result.commits_made = commits_made

                    # Check stall condition
                    if commits_made == 0:
                        self.no_commit_counts[subtask.id] = (
                            self.no_commit_counts.get(subtask.id, 0) + 1
                        )
                        if (
                            self.no_commit_counts[subtask.id]
                            >= self.config.stall_detection.max_no_commit_sessions
                        ):
                            msg = (
                                f"Subtask {subtask.id} stalled: "
                                f"{self.no_commit_counts[subtask.id]} sessions with no commits"
                            )
                            raise StallDetectedError(msg, TerminationReason.STALLED)
                    else:
                        self.no_commit_counts[subtask.id] = 0
                        self.state.total_commits += commits_made

                    # Handle session result
                    if session_result.status == SessionStatus.COMPLETE:
                        # Validate completion
                        if validate_completion(session_result.events, self.config.backpressure):
                            # Run per-subtask review if enabled
                            review_passed = True
                            if self.config.review.enabled and self.config.review.per_subtask:
                                logger.info(f"Running per-subtask review for {subtask.id}")
                                subtask_baseline = commit_before
                                review_passed = run_review_loop(
                                    self.config, subtask, self.project_dir, subtask_baseline
                                )

                            if review_passed:
                                self.plan_store.mark_complete(subtask.id)
                                self.recovery_store.record_good_commit(
                                    self._get_commit_hash(), subtask.id
                                )
                                review_msg = (
                                    "and reviewed" if self.config.review.per_subtask else ""
                                )
                                logger.info(
                                    f"Session {self.state.iteration}: "
                                    f"Subtask {subtask.id} completed {review_msg} successfully"
                                )
                            else:
                                logger.warning(f"Subtask {subtask.id} completed but failed review")
                                self.state.consecutive_failures += 1
                        else:
                            logger.warning(
                                f"Subtask {subtask.id} claimed done but failed validation"
                            )
                            self.state.consecutive_failures += 1
                    elif session_result.status == SessionStatus.BLOCKED:
                        logger.warning(f"Subtask {subtask.id} blocked")
                        self.plan_store.mark_failed(subtask.id)
                        self.state.consecutive_failures += 1
                    else:
                        self.state.consecutive_failures += 1

                    # Check consecutive failures
                    if (
                        self.state.consecutive_failures
                        >= self.config.stall_detection.max_consecutive_failures
                    ):
                        raise StallDetectedError(
                            f"{self.state.consecutive_failures} consecutive failures",
                            TerminationReason.CONSECUTIVE_FAILURES,
                        )

                except SessionError as e:
                    logger.error(f"Session error: {e}")
                    self.state.consecutive_failures += 1

                # Delay between sessions
                time.sleep(self.config.orchestrator.session_delay_seconds)

            # Max iterations reached
            return TerminationReason.MAX_ITERATIONS

        except StallDetectedError as e:
            logger.error(f"Stall detected: {e}")
            self.status_store.mark_failed(str(e))
            return e.termination_reason
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            self.status_store.mark_failed(str(e))
            return TerminationReason.ERROR

    def _run_session(self, subtask_id: str, description: str) -> SessionResult:
        """Run a single coding session.

        Args:
            subtask_id: ID of subtask to work on
            description: Subtask description

        Returns:
            SessionResult with status and events
        """
        # Prepare prompt
        memory_context = self.memory_store.format_for_injection(self.config.memory.max_tokens)
        failed_approaches = self.recovery_store.get_failed_approaches(subtask_id)
        attempt_number = self.recovery_store.get_attempt_count(subtask_id) + 1

        failed_section = ""
        if failed_approaches:
            failed_section = "## Previous Failed Approaches\n" + "\n".join(
                f"- {approach}" for approach in failed_approaches
            )

        prompt = create_agent_prompt(
            "coder",
            project_dir=self.project_dir,
            subtask_id=subtask_id,
            subtask_description=description,
            attempt_number=str(attempt_number),
            memory_context=memory_context,
            failed_approaches_section=failed_section,
        )

        # Run session (pass prompt directly, no file needed)
        start_time = time.time()
        try:
            result = run_claude_session(
                prompt,
                self.project_dir,
                self.config.orchestrator.session_timeout_seconds,
            )
        finally:
            duration = time.time() - start_time

        # Parse actual output from Claude session
        output = result.stdout if result.stdout else ""
        events = parse_events(output)

        # Determine status from events and return code
        if result.returncode == 0 and has_completion_event(events):
            status = SessionStatus.COMPLETE
        elif has_blocked_event(events):
            status = SessionStatus.BLOCKED
        elif result.returncode == 0:
            # Succeeded but no completion event - keep working
            status = SessionStatus.CONTINUE
        else:
            status = SessionStatus.FAILED

        # Record attempt for recovery tracking
        success = status == SessionStatus.COMPLETE
        error_msg = (
            None if success else output[-500:] if output else None
        )  # Last 500 chars of error
        commit_hash = self._get_commit_hash() if success else None

        self.recovery_store.record_attempt(
            subtask_id=subtask_id,
            session=self.state.iteration,
            success=success,
            approach=description,
            commit_hash=commit_hash,
            error_message=error_msg,
        )

        return SessionResult(
            status=status,
            output=output,
            commits_made=0,  # Will be set by caller
            events=events,
            duration_seconds=duration,
        )

    def _run_initializer_session(self, task_description: str) -> SessionResult:
        """Run initializer session to create implementation plan.

        Args:
            task_description: The task to implement

        Returns:
            SessionResult with status and events
        """
        logger.info(
            f"Session {self.state.iteration}: Running Initializer for task: {task_description}"
        )

        # Create initializer prompt
        prompt = create_agent_prompt(
            "initializer",
            project_dir=self.project_dir,
            task_description=task_description,
        )

        # Run session (pass prompt directly, no file needed)
        start_time = time.time()
        try:
            result = run_claude_session(
                prompt,
                self.project_dir,
                self.config.orchestrator.session_timeout_seconds,
            )
        finally:
            duration = time.time() - start_time

        # Parse actual output from initializer session
        output = result.stdout if result.stdout else ""
        events = parse_events(output)

        # Determine status
        if result.returncode == 0 and has_completion_event(events):
            status = SessionStatus.COMPLETE
        elif result.returncode == 0:
            status = SessionStatus.CONTINUE
        else:
            status = SessionStatus.FAILED

        return SessionResult(
            status=status,
            output=output,
            commits_made=0,
            events=events,
            duration_seconds=duration,
        )

    def _get_commit_hash(self) -> str:
        """Get current commit hash or empty string if not git repo."""
        if is_git_repo(self.project_dir):
            try:
                return get_current_commit(self.project_dir)
            except Exception:
                return ""
        return ""

    def _count_commits_since(self, since_commit: str) -> int:
        """Count commits since a given commit."""
        if not since_commit or not is_git_repo(self.project_dir):
            return 0
        try:
            return count_new_commits(self.project_dir, since_commit)
        except Exception:
            return 0

    def _update_status(self, subtask_id: str, description: str, status_str: str) -> None:
        """Update status file."""
        completed, total = self.plan_store.get_completion_stats()
        status = StatusInfo(
            pid=os.getpid(),
            iteration=self.state.iteration,
            subtask_id=subtask_id,
            subtask_description=description,
            status=status_str,
            total_commits=self.state.total_commits,
            completed_subtasks=completed,
            total_subtasks=total,
        )
        self.status_store.update(status)
