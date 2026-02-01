"""Implementation plan persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from rasen.exceptions import StoreError
from rasen.models import ImplementationPlan, Subtask, SubtaskStatus
from rasen.stores._atomic import atomic_write, file_lock


class PlanStore:
    """Manages implementation plan persistence."""

    def __init__(self, rasen_dir: Path) -> None:
        """Initialize plan store.

        Args:
            rasen_dir: Path to .rasen directory.
        """
        self.path = rasen_dir / "state.json"
        self.rasen_dir = rasen_dir

    def load(self) -> ImplementationPlan | None:
        """Load implementation plan from disk.

        Returns:
            ImplementationPlan or None if not exists.

        Raises:
            StoreError: If file exists but is corrupted.
        """
        if not self.path.exists():
            return None

        try:
            with file_lock(self.path, shared=True):
                content = self.path.read_text()
                return ImplementationPlan.model_validate_json(content)
        except Exception as e:
            raise StoreError(f"Failed to load plan: {e}") from e

    def save(self, plan: ImplementationPlan) -> None:
        """Save implementation plan atomically.

        Args:
            plan: Plan to save.
        """
        plan.updated_at = datetime.now(UTC)
        self.rasen_dir.mkdir(parents=True, exist_ok=True)

        with file_lock(self.path, shared=False):
            atomic_write(self.path, plan.model_dump_json(indent=2))

    def has_plan(self) -> bool:
        """Check if plan exists.

        Returns:
            True if plan file exists
        """
        return self.path.exists()

    def get_next_subtask(self) -> Subtask | None:
        """Get next subtask to work on.

        Priority:
        1. IN_PROGRESS tasks (resume interrupted work)
        2. PENDING tasks (new work)

        Returns:
            Next subtask to work on, or None if all complete.
        """
        plan = self.load()
        if plan is None:
            return None

        # First, check for in_progress tasks (resume interrupted work)
        for subtask in plan.subtasks:
            if subtask.status == SubtaskStatus.IN_PROGRESS:
                return subtask

        # Then, check for pending tasks
        for subtask in plan.subtasks:
            if subtask.status == SubtaskStatus.PENDING:
                return subtask

        return None

    def mark_in_progress(self, subtask_id: str) -> None:
        """Mark subtask as in progress.

        Args:
            subtask_id: ID of subtask to update
        """
        self._update_subtask_status(subtask_id, SubtaskStatus.IN_PROGRESS)

    def mark_complete(self, subtask_id: str) -> None:
        """Mark subtask as completed.

        Args:
            subtask_id: ID of subtask to update
        """
        self._update_subtask_status(subtask_id, SubtaskStatus.COMPLETED)

    def mark_failed(self, subtask_id: str) -> None:
        """Mark subtask as failed.

        Args:
            subtask_id: ID of subtask to update
        """
        self._update_subtask_status(subtask_id, SubtaskStatus.FAILED)

    def increment_attempts(self, subtask_id: str, approach: str) -> None:
        """Increment attempt count and record approach.

        Args:
            subtask_id: ID of subtask to update
            approach: Description of approach taken
        """
        plan = self.load()
        if plan is None:
            raise StoreError("No plan to update")

        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                subtask.attempts += 1
                subtask.last_approach = approach
                break

        self.save(plan)

    def get_completion_stats(self) -> tuple[int, int]:
        """Get completion statistics.

        Returns:
            Tuple of (completed_count, total_count).
        """
        plan = self.load()
        if plan is None:
            return (0, 0)

        completed = sum(1 for s in plan.subtasks if s.status == SubtaskStatus.COMPLETED)
        return (completed, len(plan.subtasks))

    def _update_subtask_status(self, subtask_id: str, status: SubtaskStatus) -> None:
        """Update subtask status.

        Args:
            subtask_id: ID of subtask to update
            status: New status
        """
        plan = self.load()
        if plan is None:
            raise StoreError("No plan to update")

        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                subtask.status = status
                break

        self.save(plan)
