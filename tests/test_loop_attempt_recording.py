"""Tests for attempt recording in orchestration loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from rasen.claude_runner import SessionRunResult
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
from rasen.qa import QALoopResult
from rasen.review import ReviewLoopResult


def _create_mock_session_result(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    session_id: str = "test-session-123",
    input_tokens: int = 100,
    output_tokens: int = 200,
) -> SessionRunResult:
    """Create a properly typed SessionRunResult for tests."""
    return SessionRunResult(
        args=["claude", "chat"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        session_id=session_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


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
        result = _create_mock_session_result(
            returncode=0,
            stdout='<event topic="build.done">tests: pass, lint: pass</event>',
        )
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
        result = _create_mock_session_result(
            returncode=1,
            stdout="Error: failed to compile\nTypeError: something went wrong",
        )
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
        result = _create_mock_session_result(
            returncode=0,
            stdout='<event topic="build.blocked">Missing API key</event>',
        )
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
        result1 = _create_mock_session_result(
            returncode=1,
            stdout="Error: first attempt failed",
            session_id="session-1",
        )

        # Second attempt succeeds
        result2 = _create_mock_session_result(
            returncode=0,
            stdout='<event topic="build.done">tests: pass</event>',
            session_id="session-2",
        )

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
        result = _create_mock_session_result(
            returncode=0,
            stdout='<event topic="build.done">complete</event>',
        )
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


@pytest.fixture
def test_config_with_review() -> Config:
    """Create test configuration with review enabled."""
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
        review=ReviewConfig(enabled=True, per_subtask=True, max_loops=2),
        qa=QAConfig(enabled=False),
        worktree=WorktreeConfig(),
        background=BackgroundConfig(),
    )


def test_review_rejection_records_attempt(test_config_with_review, test_project):
    """Test that review rejection records attempt with feedback."""
    loop = OrchestrationLoop(test_config_with_review, test_project, "Test task")

    # Simulate review rejection by calling record_attempt directly
    # (as would happen in the loop when review fails)
    feedback = "Code has security vulnerability in auth module"
    loop.recovery_store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="Subtask completed but review rejected",
        error_message=f"Review rejected: {feedback}",
    )

    # Verify attempt was recorded with review feedback
    history = loop.recovery_store._load_history()
    assert len(history.records) == 1

    record = history.records[0]
    assert record.subtask_id == "task-1"
    assert record.success is False
    assert "review rejected" in record.approach.lower()
    assert "security vulnerability" in record.error_message


def test_review_loop_result_contains_feedback():
    """Test that ReviewLoopResult properly stores feedback."""
    result = ReviewLoopResult(passed=False, feedback="Missing error handling")
    assert result.passed is False
    assert result.feedback == "Missing error handling"

    result_passed = ReviewLoopResult(passed=True)
    assert result_passed.passed is True
    assert result_passed.feedback is None


def test_qa_rejection_records_attempt(test_config, test_project):
    """Test that QA rejection records attempt with issues."""
    loop = OrchestrationLoop(test_config, test_project, "Test task")

    # Simulate QA rejection
    issues = ["Test coverage below 60%", "Missing integration tests"]
    issues_summary = "; ".join(issues)
    loop.recovery_store.record_attempt(
        subtask_id="qa-validation",
        session=5,
        success=False,
        approach="Build-wide QA validation",
        error_message=f"QA rejected: {issues_summary}",
    )

    # Verify attempt was recorded with QA issues
    history = loop.recovery_store._load_history()
    assert len(history.records) == 1

    record = history.records[0]
    assert record.subtask_id == "qa-validation"
    assert record.success is False
    assert "QA validation" in record.approach
    assert "Test coverage" in record.error_message
    assert "integration tests" in record.error_message


def test_qa_loop_result_contains_issues():
    """Test that QALoopResult properly stores issues."""
    result = QALoopResult(passed=False, issues=["Missing tests", "Low coverage"])
    assert result.passed is False
    assert len(result.issues) == 2
    assert "Missing tests" in result.issues

    result_passed = QALoopResult(passed=True)
    assert result_passed.passed is True
    assert len(result_passed.issues) == 0
