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


class SubtaskReview(BaseModel):
    """Review state for a single subtask (when per_subtask review is enabled)."""

    status: str = "pending"  # pending, approved, changes_requested
    feedback: list[str] = Field(default_factory=list)
    iteration: int = 0


class SubtaskQA(BaseModel):
    """QA state for a single subtask (when per_subtask QA is enabled)."""

    status: str = "pending"  # pending, approved, rejected
    issues: list[str] = Field(default_factory=list)
    iteration: int = 0


class Subtask(BaseModel):
    """A single subtask in the implementation plan."""

    id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING
    attempts: int = 0
    last_approach: str | None = None
    # Optional fields for richer task information
    title: str | None = None
    files: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    # Task-level review (used when config.review.per_subtask=true)
    review: SubtaskReview | None = None
    # Task-level QA (used when config.qa.per_subtask=true)
    qa: SubtaskQA | None = None


class ReviewState(BaseModel):
    """State of code review validation."""

    status: str = "pending"  # pending, approved, changes_requested
    feedback: list[str] = Field(default_factory=list)
    iteration: int = 0
    last_reviewed_subtask: str | None = None


class QAState(BaseModel):
    """State of QA validation."""

    status: str = "pending"  # pending, approved, rejected
    issues: list[str] = Field(default_factory=list)
    iteration: int = 0
    recurring_issues: list[str] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    """A single memory entry (decision or learning)."""

    subtask_id: str
    content: str


class MemoryState(BaseModel):
    """Cross-session memory for important decisions and learnings."""

    decisions: list[MemoryEntry] = Field(default_factory=list)
    learnings: list[MemoryEntry] = Field(default_factory=list)


class ImplementationPlan(BaseModel):
    """The full implementation plan with subtasks."""

    task_name: str
    subtasks: list[Subtask]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Optional fields for additional context
    project: str | None = None
    description: str | None = None
    notes: list[str] = Field(default_factory=list)
    # Separate sections for review and QA state
    review: ReviewState = Field(default_factory=ReviewState)
    qa: QAState = Field(default_factory=QAState)
    # Cross-session memory (max 5 each by default, configurable)
    memory: MemoryState = Field(default_factory=MemoryState)
    # Session metrics tracking
    metrics: AggregateMetrics | None = None
    session_history: list[SessionMetrics] = Field(default_factory=list)


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


class SessionMetrics(BaseModel):
    """Metrics for a single agent session."""

    session_id: str
    agent_type: str  # "initializer", "coder", "reviewer", "qa"
    subtask_id: str | None = None
    duration_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"  # "running", "completed", "failed", "timeout"


class AggregateMetrics(BaseModel):
    """Aggregate metrics across all sessions."""

    total_sessions: int = 0
    total_duration_seconds: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    sessions_by_agent: dict[str, int] = Field(default_factory=dict)
    tokens_by_agent: dict[str, int] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
