"""Domain models for RASEN orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TerminationReason(str, Enum):
    """Reasons for loop termination."""

    COMPLETE = "complete"
    MAX_ITERATIONS = "max_iterations"
    MAX_RUNTIME = "max_runtime"
    STALLED = "stalled"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    LOOP_THRASHING = "loop_thrashing"
    USER_CANCELLED = "user_cancelled"
    SESSION_TIMEOUT = "session_timeout"
    ERROR = "error"


class SessionStatus(str, Enum):
    """Status of a completed session."""

    CONTINUE = "continue"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SubtaskStatus(str, Enum):
    """Status of a subtask."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Subtask(BaseModel):
    """A single subtask in the implementation plan."""

    id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING
    attempts: int = 0
    last_approach: str | None = None


class ImplementationPlan(BaseModel):
    """The full implementation plan with subtasks."""

    task_name: str
    subtasks: list[Subtask]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AttemptRecord(BaseModel):
    """Record of a single attempt at a subtask."""

    subtask_id: str
    session: int
    success: bool
    approach: str
    commit_hash: str | None = None
    error_message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Event(BaseModel):
    """Event extracted from agent output."""

    topic: str
    payload: str


class SessionResult(BaseModel):
    """Result of a single agent session."""

    status: SessionStatus
    output: str
    commits_made: int
    events: list[Event] = Field(default_factory=list)
    duration_seconds: float = 0.0


class LoopState(BaseModel):
    """Current state of the orchestration loop."""

    iteration: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    current_subtask_id: str | None = None
    completion_confirmations: int = 0
    consecutive_failures: int = 0
    total_commits: int = 0
