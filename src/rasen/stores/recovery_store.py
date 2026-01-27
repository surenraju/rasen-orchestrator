"""Recovery and attempt tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rasen.models import AttemptRecord
from rasen.stores._atomic import atomic_write, file_lock


class AttemptHistory(BaseModel):
    """Persisted attempt history."""

    records: list[AttemptRecord] = []


class GoodCommits(BaseModel):
    """Known-good commits for rollback."""

    commits: list[dict[str, Any]] = []  # {hash, subtask_id, timestamp}


class RecoveryStore:
    """Manages recovery state and attempt tracking."""

    def __init__(self, rasen_dir: Path) -> None:
        """Initialize recovery store.

        Args:
            rasen_dir: Path to .rasen directory
        """
        self.history_path = rasen_dir / "attempt_history.json"
        self.commits_path = rasen_dir / "good_commits.json"
        self.rasen_dir = rasen_dir

    def record_attempt(
        self,
        subtask_id: str,
        session: int,
        success: bool,
        approach: str,
        commit_hash: str | None = None,
    ) -> None:
        """Record an attempt for recovery context.

        Args:
            subtask_id: ID of subtask attempted
            session: Session number
            success: Whether attempt succeeded
            approach: Description of approach taken
            commit_hash: Git commit hash if successful
        """
        history = self._load_history()
        history.records.append(
            AttemptRecord(
                subtask_id=subtask_id,
                session=session,
                success=success,
                approach=approach,
                commit_hash=commit_hash,
            )
        )
        self._save_history(history)

    def get_failed_approaches(self, subtask_id: str) -> list[str]:
        """Get approaches that failed for context injection.

        Args:
            subtask_id: ID of subtask

        Returns:
            List of failed approach descriptions
        """
        history = self._load_history()
        return [r.approach for r in history.records if r.subtask_id == subtask_id and not r.success]

    def get_attempt_count(self, subtask_id: str) -> int:
        """Get total attempts for a subtask.

        Args:
            subtask_id: ID of subtask

        Returns:
            Total number of attempts
        """
        history = self._load_history()
        return sum(1 for r in history.records if r.subtask_id == subtask_id)

    def record_good_commit(self, commit_hash: str, subtask_id: str) -> None:
        """Record known-good commit for rollback.

        Args:
            commit_hash: Git commit hash
            subtask_id: ID of subtask completed
        """
        commits = self._load_commits()
        commits.commits.append(
            {
                "hash": commit_hash,
                "subtask_id": subtask_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self._save_commits(commits)

    def get_last_good_commit(self) -> str | None:
        """Get most recent good commit for rollback.

        Returns:
            Commit hash or None if no commits recorded
        """
        commits = self._load_commits()
        if commits.commits:
            last_commit = commits.commits[-1]["hash"]
            assert isinstance(last_commit, str)
            return last_commit
        return None

    def is_thrashing(self, subtask_id: str, threshold: int = 3) -> bool:
        """Detect if subtask is stuck (N consecutive failures).

        Args:
            subtask_id: ID of subtask
            threshold: Number of consecutive failures to detect

        Returns:
            True if thrashing detected
        """
        history = self._load_history()
        subtask_records = [r for r in history.records if r.subtask_id == subtask_id]

        if len(subtask_records) < threshold:
            return False

        # Check last N records
        recent = subtask_records[-threshold:]
        return all(not r.success for r in recent)

    def get_recovery_hints(self, subtask_id: str) -> list[str]:
        """Get hints for recovery based on previous attempts.

        Args:
            subtask_id: ID of subtask

        Returns:
            List of hint strings formatted for prompt injection
        """
        history = self._load_history()
        subtask_records = [r for r in history.records if r.subtask_id == subtask_id]

        if not subtask_records:
            return ["This is the first attempt at this subtask"]

        hints = [f"Previous attempts: {len(subtask_records)}"]

        # Show last 3 attempts with approach + success/fail
        recent_attempts = subtask_records[-3:]
        for i, record in enumerate(recent_attempts, 1):
            status = "SUCCESS" if record.success else "FAILED"
            hints.append(f"Attempt {i}: {record.approach} - {status}")

        # Add warning to try different approach if multiple attempts
        if len(subtask_records) >= 2:
            hints.append("\n⚠️  IMPORTANT: Try a DIFFERENT approach than previous attempts")
            hints.append(
                "Consider: different library, different pattern, or simpler implementation"
            )

        return hints

    def _load_history(self) -> AttemptHistory:
        """Load attempt history from disk."""
        if not self.history_path.exists():
            return AttemptHistory()
        with file_lock(self.history_path, shared=True):
            return AttemptHistory.model_validate_json(self.history_path.read_text())

    def _save_history(self, history: AttemptHistory) -> None:
        """Save attempt history to disk."""
        self.rasen_dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.history_path, shared=False):
            atomic_write(self.history_path, history.model_dump_json(indent=2))

    def _load_commits(self) -> GoodCommits:
        """Load good commits from disk."""
        if not self.commits_path.exists():
            return GoodCommits()
        with file_lock(self.commits_path, shared=True):
            return GoodCommits.model_validate_json(self.commits_path.read_text())

    def _save_commits(self, commits: GoodCommits) -> None:
        """Save good commits to disk."""
        self.rasen_dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.commits_path, shared=False):
            atomic_write(self.commits_path, commits.model_dump_json(indent=2))
