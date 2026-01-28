"""Tests for code review loop functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
)
from rasen.models import Subtask, SubtaskStatus
from rasen.review import ReviewResult, run_review_loop
from rasen.stores.status_store import StatusInfo, StatusStore


@pytest.fixture
def test_config_review_disabled(tmp_path: Path) -> Config:
    """Create test configuration with review disabled."""
    return Config(
        project=ProjectConfig(
            name="test-project",
            root=str(tmp_path),
        ),
        orchestrator=OrchestratorConfig(
            max_iterations=10,
            max_runtime_seconds=300,
            session_delay_seconds=0,
            session_timeout_seconds=60,
            idle_timeout_seconds=30,
        ),
        agent=AgentConfig(
            model="claude-sonnet-4-20250514",
            max_thinking_tokens=4096,
        ),
        memory=MemoryConfig(
            enabled=True,
            path=str(tmp_path / ".rasen" / "memories.md"),
            max_tokens=1000,
        ),
        backpressure=BackpressureConfig(
            require_tests=True,
            require_lint=True,
        ),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=3,
            max_consecutive_failures=5,
        ),
        background=BackgroundConfig(
            status_file=str(tmp_path / ".rasen" / "status.json"),
            pid_file=str(tmp_path / ".rasen" / "rasen.pid"),
            log_file=str(tmp_path / ".rasen" / "rasen.log"),
        ),
        review=ReviewConfig(
            enabled=False,  # DISABLED
            max_loops=3,
        ),
        qa=QAConfig(
            enabled=True,
            max_iterations=10,
            recurring_issue_threshold=3,
        ),
    )


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create test project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    rasen_dir = project_dir / ".rasen"
    rasen_dir.mkdir()
    return project_dir


@pytest.fixture
def sample_subtask() -> Subtask:
    """Create a sample subtask."""
    return Subtask(
        id="test-subtask-1",
        description="Implement feature X",
        status=SubtaskStatus.IN_PROGRESS,
    )


def test_review_loop_disabled(
    test_config_review_disabled: Config,
    test_project: Path,
    sample_subtask: Subtask,
) -> None:
    """Test that review loop returns True immediately when review is disabled.

    Target: Lines 60-62 in review.py
    Verify:
    - Returns True immediately
    - No reviewer sessions are called
    - No coder fix sessions are called
    """
    # Mock the session runners to ensure they are NOT called
    with (
        patch("rasen.review._run_reviewer_session") as mock_reviewer,
        patch("rasen.review._run_coder_fix_session") as mock_coder_fix,
    ):
        # Run review loop with disabled config
        result = run_review_loop(
            config=test_config_review_disabled,
            subtask=sample_subtask,
            project_dir=test_project,
            baseline_commit="abc123",
        )

        # Verify return value is passed (approved by default when disabled)
        assert result.passed is True

        # Verify no sessions were called
        mock_reviewer.assert_not_called()
        mock_coder_fix.assert_not_called()


@pytest.fixture
def test_config_review_enabled(tmp_path: Path) -> Config:
    """Create test configuration with review enabled."""
    return Config(
        project=ProjectConfig(
            name="test-project",
            root=str(tmp_path),
        ),
        orchestrator=OrchestratorConfig(
            max_iterations=10,
            max_runtime_seconds=300,
            session_delay_seconds=0,
            session_timeout_seconds=60,
            idle_timeout_seconds=30,
        ),
        agent=AgentConfig(
            model="claude-sonnet-4-20250514",
            max_thinking_tokens=4096,
        ),
        memory=MemoryConfig(
            enabled=True,
            path=str(tmp_path / ".rasen" / "memories.md"),
            max_tokens=1000,
        ),
        backpressure=BackpressureConfig(
            require_tests=True,
            require_lint=True,
        ),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=3,
            max_consecutive_failures=5,
        ),
        background=BackgroundConfig(
            status_file=str(tmp_path / ".rasen" / "status.json"),
            pid_file=str(tmp_path / ".rasen" / "rasen.pid"),
            log_file=str(tmp_path / ".rasen" / "rasen.log"),
        ),
        review=ReviewConfig(
            enabled=True,  # ENABLED
            max_loops=3,
        ),
        qa=QAConfig(
            enabled=True,
            max_iterations=10,
            recurring_issue_threshold=3,
        ),
    )


def test_review_loop_updates_status(
    test_config_review_enabled: Config,
    test_project: Path,
    sample_subtask: Subtask,
) -> None:
    """Test status file updates during review loop.

    Target: Lines 69-76 in review.py
    Verify:
    - Status.json updated with 'Review 1/3' phase on first iteration
    - Status.json updated with 'Review 2/3' phase on second iteration
    - Reviewer approves on second try
    - Review loop returns True after approval
    """
    # Create initial status file
    status_file = test_project / ".rasen" / "status.json"
    status_store = StatusStore(status_file)
    initial_status = StatusInfo(
        pid=12345,
        iteration=1,
        subtask_id=sample_subtask.id,
        subtask_description=sample_subtask.description,
        current_phase="Coding",
        status="running",
        total_commits=0,
        completed_subtasks=0,
        total_subtasks=1,
    )
    status_store.update(initial_status)

    # Track which iteration we're on
    call_count = 0

    def mock_reviewer_side_effect(*_args, **_kwargs):
        """Mock reviewer that rejects first, approves second."""
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: request changes
            return ReviewResult(approved=False, feedback="Please fix issue X")
        # Second call: approve
        return ReviewResult(approved=True)

    # Mock both session runners
    with (
        patch("rasen.review._run_reviewer_session", side_effect=mock_reviewer_side_effect),
        patch("rasen.review._run_coder_fix_session") as mock_coder_fix,
    ):
        # Run review loop
        result = run_review_loop(
            config=test_config_review_enabled,
            subtask=sample_subtask,
            project_dir=test_project,
            baseline_commit="abc123",
        )

        # Verify review loop succeeded (approved on second try)
        assert result.passed is True

        # Verify reviewer was called twice
        assert call_count == 2

        # Verify coder fix was called once (between reviews)
        assert mock_coder_fix.call_count == 1

    # Verify status file updates
    # Read final status
    final_status = status_store.load()
    assert final_status is not None
    # Final status should show Review 2/3 (last iteration before approval)
    assert final_status.current_phase == "Review 2/3"
