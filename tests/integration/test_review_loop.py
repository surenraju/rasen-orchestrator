"""Integration tests for review loop (Coder ↔ Reviewer).

Tests the code review workflow:
1. Reviewer validates changes (read-only)
2. If changes_requested → Coder fixes
3. If approved → continue
4. Max iterations limit
"""

from __future__ import annotations

import json
import os
import subprocess
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
from rasen.events import Event
from rasen.models import Subtask
from rasen.review import run_review_loop


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a git repository for testing."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create prompts directory with templates
    prompts_dir = repo_dir / "prompts"
    prompts_dir.mkdir()

    (prompts_dir / "reviewer.md").write_text("""
# Reviewer Prompt

Subtask: {subtask_id}
Description: {subtask_description}

Diff:
{git_diff}

Review the code and emit either:
<event topic="review.approved">LGTM</event>
or
<event topic="review.changes_requested">Feedback here</event>
    """)

    (prompts_dir / "coder.md").write_text("""
# Coder Prompt

Subtask: {subtask_id}
Description: {subtask_description}
Attempt: {attempt_number}

Memory: {memory_context}
Failed Approaches: {failed_approaches_section}
    """)

    # Initial commit
    (repo_dir / "README.md").write_text("# Test Project")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create .rasen directory
    rasen_dir = repo_dir / ".rasen"
    rasen_dir.mkdir()

    # Create initial status file with all required fields
    status = {
        "pid": os.getpid(),
        "iteration": 1,
        "subtask_id": None,
        "subtask_description": None,
        "current_phase": "Testing",
        "last_activity": "2025-01-01T00:00:00+00:00",
        "status": "running",
        "total_commits": 0,
        "completed_subtasks": 0,
        "total_subtasks": 1,
    }
    (rasen_dir / "status.json").write_text(json.dumps(status, indent=2))

    return repo_dir


@pytest.fixture
def test_config_with_review(git_repo: Path) -> Config:
    """Create test configuration with review enabled."""
    return Config(
        project=ProjectConfig(
            name="test-project",
            root=str(git_repo),
        ),
        orchestrator=OrchestratorConfig(
            max_iterations=3,
            session_delay_seconds=0,  # No delay in tests
        ),
        agent=AgentConfig(
            model="claude-sonnet-4-20250514",
        ),
        worktree=WorktreeConfig(enabled=False),
        memory=MemoryConfig(
            enabled=False,
            path=str(git_repo / ".rasen" / "memories.md"),
        ),
        backpressure=BackpressureConfig(
            require_tests=False,
            require_lint=False,
        ),
        background=BackgroundConfig(
            enabled=False,
            pid_file=str(git_repo / ".rasen" / "rasen.pid"),
            log_file=str(git_repo / ".rasen" / "rasen.log"),
            status_file=str(git_repo / ".rasen" / "status.json"),
        ),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=2,
            max_consecutive_failures=3,
        ),
        review=ReviewConfig(
            enabled=True,
            max_loops=3,
        ),
        qa=QAConfig(enabled=False),
    )


@pytest.fixture
def sample_subtask() -> Subtask:
    """Create a sample subtask for testing."""
    return Subtask(
        id="test-subtask-1",
        description="Implement test feature",
        status="in_progress",
        attempts=1,
        last_approach=None,
    )


@pytest.fixture
def mock_reviewer_approved():
    """Mock reviewer session that approves changes.

    Returns a mock that simulates a successful reviewer session
    that emits review.approved event.
    """
    with patch("rasen.review.run_claude_session") as mock:
        result = MagicMock()
        result.returncode = 0
        mock.return_value = result

        # Mock parse_events to return approval
        with patch("rasen.review.parse_events") as mock_parse:
            mock_parse.return_value = [Event(topic="review.approved", payload="LGTM")]
            yield mock


@pytest.fixture
def mock_reviewer_changes_requested():
    """Mock reviewer session that requests changes.

    Returns a mock that simulates a reviewer session
    that emits review.changes_requested event.
    """
    with patch("rasen.review.run_claude_session") as mock:
        result = MagicMock()
        result.returncode = 0
        mock.return_value = result

        # Mock parse_events to return changes requested
        with patch("rasen.review.parse_events") as mock_parse:
            mock_parse.return_value = [
                Event(topic="review.changes_requested", payload="Please fix formatting")
            ]
            yield mock


def test_review_loop_approves_on_first_try(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test happy path where reviewer approves immediately.

    This tests the review loop when the reviewer approves changes
    on the first iteration. It verifies:
    - run_review_loop returns True (approved)
    - Reviewer session is called exactly once
    - No coder fix sessions are called (no need to fix)
    - Review loop completes successfully
    """
    # Get baseline commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    baseline_commit = result.stdout.strip()

    # Mock reviewer session to approve on first try
    with patch("rasen.review.run_claude_session") as mock_session:
        # Set up successful session result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_session.return_value = mock_result

        # Mock parse_events to return approval
        with patch("rasen.review.parse_events") as mock_parse:
            mock_parse.return_value = [Event(topic="review.approved", payload="LGTM")]

            # Run review loop
            result = run_review_loop(
                test_config_with_review,
                sample_subtask,
                git_repo,
                baseline_commit,
            )

            # Assertions
            assert result is True, "Review loop should return True when approved"
            assert mock_session.call_count == 1, "Reviewer session should be called exactly once"

            # Verify the prompt was created correctly (first call is reviewer)
            call_args = mock_session.call_args_list[0]
            prompt_text = call_args[0][0]  # First positional argument
            assert "test-subtask-1" in prompt_text, "Subtask ID should be in prompt"
            assert "Implement test feature" in prompt_text, (
                "Subtask description should be in prompt"
            )

            # Verify no fix sessions were called (only one reviewer call)
            # If there were fix sessions, we'd see more calls
            assert mock_session.call_count == 1, "No coder fix sessions should be called"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
