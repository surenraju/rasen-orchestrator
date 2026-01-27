"""Tests for RASEN Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rasen.models import (
    Event,
    ImplementationPlan,
    LoopState,
    SessionResult,
    SessionStatus,
    Subtask,
    SubtaskStatus,
    TerminationReason,
)


def test_termination_reason_enum():
    """Test TerminationReason enum values."""
    assert TerminationReason.COMPLETE.value == "complete"
    assert TerminationReason.MAX_ITERATIONS.value == "max_iterations"
    assert TerminationReason.STALLED.value == "stalled"
    assert TerminationReason.CONSECUTIVE_FAILURES.value == "consecutive_failures"
    assert TerminationReason.ERROR.value == "error"


def test_session_status_enum():
    """Test SessionStatus enum values."""
    assert SessionStatus.CONTINUE.value == "continue"
    assert SessionStatus.COMPLETE.value == "complete"
    assert SessionStatus.FAILED.value == "failed"
    assert SessionStatus.BLOCKED.value == "blocked"
    assert SessionStatus.TIMEOUT.value == "timeout"


def test_subtask_status_enum():
    """Test SubtaskStatus enum values."""
    assert SubtaskStatus.PENDING.value == "pending"
    assert SubtaskStatus.IN_PROGRESS.value == "in_progress"
    assert SubtaskStatus.COMPLETED.value == "completed"
    assert SubtaskStatus.FAILED.value == "failed"


def test_event_model():
    """Test Event model."""
    event = Event(topic="build.done", payload="tests: pass")
    assert event.topic == "build.done"
    assert event.payload == "tests: pass"


def test_event_validation():
    """Test Event model requires both fields."""
    # Event allows empty strings, so test missing fields
    with pytest.raises(ValidationError):
        Event(topic="build.done")  # Missing payload should fail


def test_subtask_model():
    """Test Subtask model creation."""
    subtask = Subtask(
        id="task-1",
        description="Test task",
        status=SubtaskStatus.PENDING,
        last_approach="Using pattern X",
    )
    assert subtask.id == "task-1"
    assert subtask.description == "Test task"
    assert subtask.status == SubtaskStatus.PENDING
    assert subtask.last_approach == "Using pattern X"
    assert subtask.attempts == 0


def test_subtask_defaults():
    """Test Subtask default values."""
    subtask = Subtask(
        id="task-1",
        description="Test task",
    )
    assert subtask.status == SubtaskStatus.PENDING
    assert subtask.attempts == 0
    assert subtask.last_approach is None


def test_subtask_validation():
    """Test Subtask model validation."""
    with pytest.raises(ValidationError):
        Subtask(id="task-1")  # Missing required description field


def test_implementation_plan_model():
    """Test ImplementationPlan model."""
    plan = ImplementationPlan(
        task_name="Test project",
        subtasks=[
            Subtask(id="t1", description="Task 1", status=SubtaskStatus.PENDING),
            Subtask(id="t2", description="Task 2", status=SubtaskStatus.PENDING),
        ],
    )
    assert plan.task_name == "Test project"
    assert len(plan.subtasks) == 2
    assert isinstance(plan.created_at, datetime)
    assert isinstance(plan.updated_at, datetime)


def test_implementation_plan_timestamps():
    """Test ImplementationPlan automatic timestamps."""
    plan = ImplementationPlan(
        task_name="Test",
        subtasks=[],
    )
    assert plan.created_at.tzinfo == UTC
    assert plan.updated_at.tzinfo == UTC
    assert plan.created_at <= datetime.now(UTC)


def test_implementation_plan_empty_subtasks():
    """Test ImplementationPlan with no subtasks."""
    plan = ImplementationPlan(task_name="Empty", subtasks=[])
    assert len(plan.subtasks) == 0


def test_session_result_model():
    """Test SessionResult model."""
    events = [Event(topic="build.done", payload="Success")]
    result = SessionResult(
        status=SessionStatus.COMPLETE,
        output="Test output",
        commits_made=3,
        events=events,
        duration_seconds=45.5,
    )
    assert result.status == SessionStatus.COMPLETE
    assert result.output == "Test output"
    assert result.commits_made == 3
    assert len(result.events) == 1
    assert result.duration_seconds == 45.5


def test_session_result_defaults():
    """Test SessionResult default values."""
    result = SessionResult(
        status=SessionStatus.COMPLETE,
        output="Done",
        commits_made=0,
    )
    assert result.commits_made == 0
    assert result.events == []
    assert result.duration_seconds == 0.0


def test_loop_state_model():
    """Test LoopState model."""
    state = LoopState()
    assert state.iteration == 0
    assert state.total_commits == 0
    assert state.consecutive_failures == 0
    assert state.current_subtask_id is None


def test_loop_state_with_values():
    """Test LoopState with custom values."""
    state = LoopState(
        iteration=5,
        total_commits=12,
        consecutive_failures=2,
        current_subtask_id="task-3",
    )
    assert state.iteration == 5
    assert state.total_commits == 12
    assert state.consecutive_failures == 2
    assert state.current_subtask_id == "task-3"


def test_subtask_status_progression():
    """Test typical subtask status progression."""
    subtask = Subtask(
        id="task-1",
        description="Test",
        status=SubtaskStatus.PENDING,
    )

    # Progress through states
    subtask.status = SubtaskStatus.IN_PROGRESS
    assert subtask.status == SubtaskStatus.IN_PROGRESS

    subtask.status = SubtaskStatus.COMPLETED
    assert subtask.status == SubtaskStatus.COMPLETED


def test_subtask_attempts_increment():
    """Test incrementing subtask attempts."""
    subtask = Subtask(
        id="task-1",
        description="Test",
        status=SubtaskStatus.PENDING,
    )
    assert subtask.attempts == 0

    subtask.attempts += 1
    assert subtask.attempts == 1

    subtask.attempts += 1
    assert subtask.attempts == 2


def test_implementation_plan_json_serialization():
    """Test ImplementationPlan can be serialized to JSON."""
    plan = ImplementationPlan(
        task_name="Test",
        subtasks=[
            Subtask(id="t1", description="Task 1", status=SubtaskStatus.PENDING),
        ],
    )

    # Should not raise
    json_data = plan.model_dump()
    assert json_data["task_name"] == "Test"
    assert len(json_data["subtasks"]) == 1


def test_event_with_multiline_payload():
    """Test Event with multiline payload."""
    payload = """Line 1
Line 2
Line 3"""
    event = Event(topic="qa.rejected", payload=payload)
    assert event.payload == payload
    assert "Line 1" in event.payload
