"""Tests for attempt recording in orchestration loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rasen.config import (
    AgentConfig,
    BackgroundConfig,
    BackpressureConfig,
    Config,
    MemoryConfig,
    OrchestratorConfig,
    ProjectConfig,
    QAConfig,
    ReviewConfig,
    StallDetectionConfig,
    WorktreeConfig,
)
from rasen.loop import OrchestrationLoop
from rasen.models import SessionStatus


@pytest.fixture
def test_config() -> Config:
    """Create test configuration."""
    return Config(
        project=ProjectConfig(),
        agent=AgentConfig(model="claude-sonnet-4"),
        orchestrator=OrchestratorConfig(
            max_iterations=10,
            session_timeout_seconds=300,
            session_delay_seconds=0,
        ),
        backpressure=BackpressureConfig(require_tests=False, require_lint=False),
        memory=MemoryConfig(path=".rasen/memory.json", max_tokens=1000),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=3,
            max_consecutive_failures=5,
        ),
        review=ReviewConfig(enabled=False),
        qa=QAConfig(enabled=False),
        worktree=WorktreeConfig(),
        background=BackgroundConfig(),
    )


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create test project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # Create prompts directory
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir()

    # Create prompt templates
    (prompts_dir / "coder.md").write_text("""
# Coder Prompt
Subtask: {subtask_id}
Description: {subtask_description}
    """)

    return project_dir


def test_run_session_records_successful_attempt(test_config, test_project):
    """Test that _run_session records successful attempt."""
    loop = OrchestrationLoop(test_config, test_project, "Test task")

    # Mock Claude session to return success
    with patch("rasen.loop.run_claude_session") as mock_session:
        result = MagicMock()
        result.returncode = 0
        result.stdout = '<event topic="build.done">tests: pass, lint: pass</event>'
        mock_session.return_value = result

        # Run session
        session_result = loop._run_session("task-1", "Implement feature X")

        # Verify session was successful
        assert session_result.status == SessionStatus.COMPLETE

        # Verify attempt was recorded
        history = loop.recovery_store._load_history()
        assert len(history.records) == 1

        record = history.records[0]
        assert record.subtask_id == "task-1"
        assert record.session == loop.state.iteration
        assert record.success is True
        assert record.approach == "Implement feature X"
        assert record.error_message is None


def test_run_session_records_failed_attempt(test_config, test_project):
    """Test that _run_session records failed attempt with error."""
    loop = OrchestrationLoop(test_config, test_project, "Test task")

    # Mock Claude session to return failure
    with patch("rasen.loop.run_claude_session") as mock_session:
        result = MagicMock()
        result.returncode = 1
        result.stdout = "Error: failed to compile\nTypeError: something went wrong"
        mock_session.return_value = result

        # Run session
        session_result = loop._run_session("task-1", "Implement feature X")

        # Verify session failed
        assert session_result.status == SessionStatus.FAILED

        # Verify attempt was recorded with error
        history = loop.recovery_store._load_history()
        assert len(history.records) == 1

        record = history.records[0]
        assert record.subtask_id == "task-1"
        assert record.session == loop.state.iteration
        assert record.success is False
        assert record.approach == "Implement feature X"
        assert record.error_message is not None
        assert "TypeError: something went wrong" in record.error_message


def test_run_session_records_blocked_attempt(test_config, test_project):
    """Test that _run_session records blocked attempt."""
    loop = OrchestrationLoop(test_config, test_project, "Test task")

    # Mock Claude session to return blocked
    with patch("rasen.loop.run_claude_session") as mock_session:
        result = MagicMock()
        result.returncode = 0
        result.stdout = '<event topic="build.blocked">Missing API key</event>'
        mock_session.return_value = result

        # Run session
        session_result = loop._run_session("task-1", "Implement feature X")

        # Verify session was blocked
        assert session_result.status == SessionStatus.BLOCKED

        # Verify attempt was recorded as failure
        history = loop.recovery_store._load_history()
        assert len(history.records) == 1

        record = history.records[0]
        assert record.subtask_id == "task-1"
        assert record.success is False
        assert record.approach == "Implement feature X"


def test_run_session_records_multiple_attempts(test_config, test_project):
    """Test that _run_session records multiple attempts correctly."""
    loop = OrchestrationLoop(test_config, test_project, "Test task")

    with patch("rasen.loop.run_claude_session") as mock_session:
        # First attempt fails
        result1 = MagicMock()
        result1.returncode = 1
        result1.stdout = "Error: first attempt failed"

        # Second attempt succeeds
        result2 = MagicMock()
        result2.returncode = 0
        result2.stdout = '<event topic="build.done">tests: pass</event>'

        mock_session.side_effect = [result1, result2]

        # Run first session
        loop.state.iteration = 1
        loop._run_session("task-1", "First approach")

        # Run second session
        loop.state.iteration = 2
        loop._run_session("task-1", "Second approach")

        # Verify both attempts were recorded
        history = loop.recovery_store._load_history()
        assert len(history.records) == 2

        # First attempt should be failure
        assert history.records[0].subtask_id == "task-1"
        assert history.records[0].session == 1
        assert history.records[0].success is False
        assert history.records[0].approach == "First approach"

        # Second attempt should be success
        assert history.records[1].subtask_id == "task-1"
        assert history.records[1].session == 2
        assert history.records[1].success is True
        assert history.records[1].approach == "Second approach"


def test_run_session_records_different_subtasks(test_config, test_project):
    """Test that _run_session records attempts for different subtasks."""
    loop = OrchestrationLoop(test_config, test_project, "Test task")

    with patch("rasen.loop.run_claude_session") as mock_session:
        result = MagicMock()
        result.returncode = 0
        result.stdout = '<event topic="build.done">complete</event>'
        mock_session.return_value = result

        # Run sessions for different subtasks
        loop.state.iteration = 1
        loop._run_session("task-1", "Implement feature A")

        loop.state.iteration = 2
        loop._run_session("task-2", "Implement feature B")

        # Verify both attempts were recorded with correct subtask IDs
        history = loop.recovery_store._load_history()
        assert len(history.records) == 2

        assert history.records[0].subtask_id == "task-1"
        assert history.records[0].approach == "Implement feature A"

        assert history.records[1].subtask_id == "task-2"
        assert history.records[1].approach == "Implement feature B"
