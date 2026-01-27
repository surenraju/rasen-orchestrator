"""Main orchestration loop for RASEN."""

from __future__ import annotations

import os
import time
from pathlib import Path

from rasen.claude_runner import run_claude_session
from rasen.config import Config
from rasen.events import parse_events
from rasen.exceptions import SessionError, StallDetectedError
from rasen.git import count_new_commits, get_current_commit, is_git_repo
from rasen.logging import get_logger
from rasen.models import (
    LoopState,
    SessionResult,
    SessionStatus,
    TerminationReason,
)
from rasen.prompts import create_agent_prompt
from rasen.stores.memory_store import MemoryStore
from rasen.stores.plan_store import PlanStore
from rasen.stores.recovery_store import RecoveryStore
from rasen.stores.status_store import StatusInfo, StatusStore
from rasen.validation import validate_completion

logger = get_logger(__name__)


class OrchestrationLoop:
    """Main orchestration loop that manages agent sessions."""

    def __init__(self, config: Config, project_dir: Path) -> None:
        """Initialize orchestration loop.

        Args:
            config: RASEN configuration
            project_dir: Path to project directory
        """
        self.config = config
        self.project_dir = project_dir
        self.rasen_dir = project_dir / ".rasen"

        # Initialize stores
        self.plan_store = PlanStore(self.rasen_dir)
        self.recovery_store = RecoveryStore(self.rasen_dir)
        self.memory_store = MemoryStore(Path(config.memory.path))
        self.status_store = StatusStore(Path(config.background.status_file))

        # State
        self.state = LoopState()
        self.no_commit_counts: dict[str, int] = {}

    def run(self) -> TerminationReason:
        """Run the orchestration loop until completion or termination.

        Returns:
            Reason for termination
        """
        logger.info("Starting orchestration loop")

        try:
            # Main loop
            while self.state.iteration < self.config.orchestrator.max_iterations:
                self.state.iteration += 1

                # Get next subtask
                subtask = self.plan_store.get_next_subtask()
                if not subtask:
                    # All subtasks complete
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
                            self.plan_store.mark_complete(subtask.id)
                            self.recovery_store.record_good_commit(
                                self._get_commit_hash(), subtask.id
                            )
                            logger.info(f"Subtask {subtask.id} completed successfully")
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
            Path("prompts"),
            subtask_id=subtask_id,
            subtask_description=description,
            attempt_number=str(attempt_number),
            memory_context=memory_context,
            failed_approaches_section=failed_section,
        )

        # Write prompt to temp file
        prompt_file = self.rasen_dir / f"prompt_{subtask_id}.md"
        prompt_file.write_text(prompt)

        # Run session
        start_time = time.time()
        try:
            result = run_claude_session(
                prompt_file,
                self.project_dir,
                self.config.orchestrator.session_timeout_seconds,
            )
        finally:
            duration = time.time() - start_time

        # Parse output (would need to capture stdout/stderr properly)
        # For now, simulate events based on return code
        if result.returncode == 0:
            events = [parse_events('<event topic="build.done">Session completed</event>')[0]]
            status = SessionStatus.COMPLETE
        else:
            events = []
            status = SessionStatus.FAILED

        return SessionResult(
            status=status,
            output="",  # Would capture actual output
            commits_made=0,  # Will be set by caller
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
