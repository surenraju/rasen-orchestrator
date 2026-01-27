"""Real-time status tracking for monitoring."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from rasen.stores._atomic import atomic_write


class StatusInfo(BaseModel):
    """Current orchestrator status."""

    pid: int
    iteration: int
    subtask_id: str | None
    subtask_description: str | None
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str  # "running", "paused", "completed", "failed"
    total_commits: int = 0
    completed_subtasks: int = 0
    total_subtasks: int = 0


class StatusStore:
    """Manages real-time status file for external monitoring."""

    def __init__(self, status_file: Path) -> None:
        """Initialize status store.

        Args:
            status_file: Path to status.json file
        """
        self.path = status_file

    def update(self, status: StatusInfo) -> None:
        """Update status file atomically.

        Args:
            status: Current status information
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, status.model_dump_json(indent=2))

    def load(self) -> StatusInfo | None:
        """Load current status.

        Returns:
            StatusInfo or None if file doesn't exist
        """
        if not self.path.exists():
            return None
        return StatusInfo.model_validate_json(self.path.read_text())

    def mark_completed(self) -> None:
        """Mark orchestrator as completed."""
        status = self.load()
        if status:
            status.status = "completed"
            status.last_activity = datetime.now(UTC)
            self.update(status)

    def mark_failed(self, reason: str) -> None:
        """Mark orchestrator as failed.

        Args:
            reason: Failure reason
        """
        status = self.load()
        if status:
            status.status = f"failed: {reason}"
            status.last_activity = datetime.now(UTC)
            self.update(status)
