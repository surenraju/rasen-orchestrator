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
from rasen.review import run_review_loop


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

        # Verify return value is True (approved by default when disabled)
        assert result is True

        # Verify no sessions were called
        mock_reviewer.assert_not_called()
        mock_coder_fix.assert_not_called()
