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
from rasen.exceptions import SessionError
from rasen.models import Subtask
from rasen.review import _run_coder_fix_session, _run_reviewer_session, run_review_loop


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


def _create_state_json(
    rasen_dir: Path,
    subtask_id: str,
    review_status: str = "pending",
    review_feedback: list[str] | None = None,
) -> None:
    """Helper to create state.json with review state.

    Args:
        rasen_dir: Path to .rasen directory
        subtask_id: ID of the subtask
        review_status: Review status (pending, approved, changes_requested)
        review_feedback: List of feedback items if changes_requested
    """
    plan = {
        "task_name": "Test Task",
        "subtasks": [
            {
                "id": subtask_id,
                "description": "Implement test feature",
                "status": "in_progress",
                "attempts": 1,
            }
        ],
        "review": {
            "status": review_status,
            "feedback": review_feedback or [],
            "iteration": 1,
            "last_reviewed_subtask": subtask_id,
        },
        "qa": {
            "status": "pending",
            "issues": [],
            "iteration": 0,
            "recurring_issues": [],
        },
    }
    (rasen_dir / "state.json").write_text(json.dumps(plan, indent=2))


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

    rasen_dir = git_repo / ".rasen"

    # Mock reviewer session to approve on first try
    with patch("rasen.review.run_claude_session") as mock_session:
        # Set up successful session result
        mock_result = _create_mock_session_result(returncode=0)

        # Create implementation plan with approved status
        # The mock session simulates Claude updating the JSON file
        def session_side_effect(*_args: object, **_kwargs: object) -> SessionRunResult:
            _create_state_json(rasen_dir, sample_subtask.id, "approved")
            return mock_result

        mock_session.side_effect = session_side_effect

        # Run review loop
        result = run_review_loop(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        # Assertions
        assert result.passed is True, "Review loop should pass when approved"
        assert mock_session.call_count == 1, "Reviewer session should be called exactly once"

        # Verify the prompt was created correctly (first call is reviewer)
        call_args = mock_session.call_args_list[0]
        prompt_text = call_args[0][0]  # First positional argument
        assert "test-subtask-1" in prompt_text, "Subtask ID should be in prompt"
        assert "Implement test feature" in prompt_text, "Subtask description should be in prompt"

        # Verify no fix sessions were called (only one reviewer call)
        assert mock_session.call_count == 1, "No coder fix sessions should be called"


def test_review_loop_requests_changes_then_approves(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test review iteration loop where changes requested then approved.

    This tests the review loop when the reviewer requests changes on the
    first iteration, then approves on the second iteration. It verifies:
    - run_review_loop returns True (eventually approved)
    - Reviewer session is called twice (initial review + re-review)
    - Coder fix session is called once (to address feedback)
    - Feedback is passed correctly to the coder fix session
    - Review loop completes successfully after iteration
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

    rasen_dir = git_repo / ".rasen"

    # Track call sequence to control mock behavior
    call_count = 0

    def mock_session_side_effect(*_args, **_kwargs):
        """Control mock behavior based on call sequence."""
        nonlocal call_count
        call_count += 1

        mock_result = _create_mock_session_result(returncode=0, session_id=f"session-{call_count}")

        # First call: reviewer requests changes
        if call_count == 1:
            _create_state_json(
                rasen_dir,
                sample_subtask.id,
                "changes_requested",
                ["Please fix formatting and add type hints"],
            )
        # Second call: coder fix (no JSON change needed)
        elif call_count == 2:
            pass  # Coder doesn't update review state
        # Third call: reviewer approves
        else:
            _create_state_json(rasen_dir, sample_subtask.id, "approved")

        return mock_result

    # Mock reviewer and coder sessions
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_session.side_effect = mock_session_side_effect

        # Run review loop
        result = run_review_loop(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        # Assertions
        assert result.passed is True, "Review loop should pass when eventually approved"
        assert mock_session.call_count == 3, (
            "Should have 3 calls: reviewer (changes requested), coder fix, reviewer (approved)"
        )

        # Verify the calls were made in correct order
        call_args_list = mock_session.call_args_list

        # First call: reviewer session (should contain diff, subtask info)
        first_call_prompt = call_args_list[0][0][0]
        assert "test-subtask-1" in first_call_prompt, (
            "First call should be reviewer with subtask ID"
        )
        assert "Implement test feature" in first_call_prompt, (
            "First call should include subtask description"
        )

        # Second call: coder fix session (should contain feedback)
        second_call_prompt = call_args_list[1][0][0]
        assert "Fix review issues" in second_call_prompt, (
            "Second call should be coder fix with feedback"
        )
        assert "Please fix formatting and add type hints" in second_call_prompt, (
            "Feedback should be passed to coder fix session"
        )

        # Third call: reviewer session again (re-review after fix)
        third_call_prompt = call_args_list[2][0][0]
        assert "test-subtask-1" in third_call_prompt, (
            "Third call should be reviewer re-review with subtask ID"
        )


def test_reviewer_session_reads_json_state(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test _run_reviewer_session reads review state from JSON file.

    This tests the JSON-based review state reading in _run_reviewer_session.
    It verifies:
    - status=approved in JSON → ReviewResult(approved=True)
    - status=changes_requested in JSON → ReviewResult(approved=False, feedback=...)
    - No JSON or pending status → default to approved (fail-open)
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

    rasen_dir = git_repo / ".rasen"

    # Test 1: status=approved in JSON
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_result = _create_mock_session_result(returncode=0)

        def side_effect(*_args: object, **_kwargs: object) -> SessionRunResult:
            _create_state_json(rasen_dir, sample_subtask.id, "approved")
            return mock_result

        mock_session.side_effect = side_effect

        result = _run_reviewer_session(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        assert result.approved is True, "Should be approved for status=approved in JSON"
        assert result.feedback is None, "Feedback should be None for approval"

    # Test 2: status=changes_requested in JSON
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_result = _create_mock_session_result(returncode=0)

        def side_effect2(*_args: object, **_kwargs: object) -> SessionRunResult:
            _create_state_json(
                rasen_dir,
                sample_subtask.id,
                "changes_requested",
                ["Please add type hints", "Fix formatting"],
            )
            return mock_result

        mock_session.side_effect = side_effect2

        result = _run_reviewer_session(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        assert result.approved is False, "Should not be approved for changes_requested"
        assert result.feedback == "Please add type hints\nFix formatting", (
            "Feedback should be joined from JSON array"
        )

    # Test 3: status=pending (default to approved)
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_result = _create_mock_session_result(returncode=0)

        def side_effect3(*_args: object, **_kwargs: object) -> SessionRunResult:
            _create_state_json(rasen_dir, sample_subtask.id, "pending")
            return mock_result

        mock_session.side_effect = side_effect3

        result = _run_reviewer_session(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        assert result.approved is True, "Should default to approved for pending status"
        assert result.feedback is None, "Feedback should be None for default approval"


def test_review_loop_exceeds_max_iterations(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test review loop stops at max_loops when reviewer always requests changes.

    This tests the boundary condition where the reviewer keeps requesting
    changes up to max_loops iterations. It verifies:
    - run_review_loop returns False (max loops exceeded)
    - Reviewer session is called max_loops times (3)
    - Coder fix session is called max_loops-1 times (2)
    - No fix is attempted on the last iteration
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

    rasen_dir = git_repo / ".rasen"

    # Track call counts
    session_call_count = 0

    def mock_session_side_effect(*_args, **_kwargs):
        """Mock Claude sessions - always request changes from reviewer."""
        nonlocal session_call_count
        session_call_count += 1

        mock_result = _create_mock_session_result(
            returncode=0, session_id=f"session-{session_call_count}"
        )

        # Odd calls are reviewer sessions, even calls are coder fix sessions
        # Reviewer sessions (1, 3, 5) should write changes_requested to JSON
        if session_call_count % 2 == 1:
            _create_state_json(
                rasen_dir,
                sample_subtask.id,
                "changes_requested",
                ["Please fix formatting"],
            )

        return mock_result

    # Mock reviewer and coder sessions
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_session.side_effect = mock_session_side_effect

        # Run review loop
        result = run_review_loop(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        # Assertions
        assert result.passed is False, "Review loop should fail when max iterations exceeded"
        assert result.feedback is not None, "Should have feedback when rejected"

        # With max_loops=3:
        # Iteration 1: reviewer (changes) → coder fix
        # Iteration 2: reviewer (changes) → coder fix
        # Iteration 3: reviewer (changes) → NO FIX (max reached)
        # Total: 3 reviewer calls + 2 coder fix calls = 5 calls
        assert mock_session.call_count == 5, (
            f"Expected 5 calls (3 reviewer + 2 coder fix), got {mock_session.call_count}"
        )

        # Verify the sequence of calls
        call_args_list = mock_session.call_args_list

        # First reviewer (iteration 1)
        assert "test-subtask-1" in call_args_list[0][0][0], "First call should be reviewer"
        # First coder fix
        assert "Fix review issues" in call_args_list[1][0][0], "Second call should be coder fix"
        # Second reviewer (iteration 2)
        assert "test-subtask-1" in call_args_list[2][0][0], "Third call should be reviewer"
        # Second coder fix
        assert "Fix review issues" in call_args_list[3][0][0], "Fourth call should be coder fix"
        # Third reviewer (iteration 3, final - no fix after this)
        assert "test-subtask-1" in call_args_list[4][0][0], (
            "Fifth call should be reviewer (final iteration)"
        )


def test_reviewer_session_handles_failure(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test _run_reviewer_session handles SessionError gracefully.

    This tests the error handling in _run_reviewer_session (lines 156-159).
    It verifies:
    - When run_claude_session raises SessionError
    - _run_reviewer_session catches it and logs error
    - Returns approved=True (fail-open to not block progress)
    - Feedback message indicates reviewer session failed

    This specifically tests lines 156-159 in review.py:
    - Line 156: Catch SessionError exception
    - Line 157: Log error about reviewer session failure
    - Line 158-159: Return ReviewResult(approved=True) with failure message
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

    # Mock run_claude_session to raise SessionError
    with patch("rasen.review.run_claude_session") as mock_session:
        # Simulate SessionError
        mock_session.side_effect = SessionError("Mock session error for testing")

        # Run reviewer session
        result = _run_reviewer_session(
            test_config_with_review,
            sample_subtask,
            git_repo,
            baseline_commit,
        )

        # Assertions
        assert result.approved is True, "Should be approved (fail-open) when SessionError occurs"
        assert result.feedback == "Reviewer session failed, assuming approved", (
            "Feedback should indicate reviewer session failed"
        )

        # Verify the session was called (and raised exception)
        assert mock_session.called, "run_claude_session should have been called"


def test_coder_fix_session_execution(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test _run_coder_fix_session executes successfully with correct prompt.

    This tests the coder fix session execution (lines 184-202 in review.py).
    It verifies:
    - run_claude_session is called with correct arguments
    - Prompt contains feedback from reviewer
    - Prompt contains "Fix review issues" description
    - Session timeout is passed correctly
    - Debug log directory is set correctly
    - Session completes successfully

    This specifically tests lines 184-202 in review.py:
    - Line 192: Logging coder fix session start
    - Line 195-203: Create agent prompt with feedback
    - Line 207: Set debug log directory
    - Line 209-214: Run Claude session with timeout
    """
    # Sample feedback from reviewer
    feedback = "Please add type hints and fix formatting issues"

    # Mock run_claude_session to simulate successful execution
    with patch("rasen.review.run_claude_session") as mock_session:
        # Set up successful session result with session_id attribute
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.session_id = "test-session-12345678"
        mock_session.return_value = mock_result

        # Run coder fix session
        _run_coder_fix_session(
            test_config_with_review,
            sample_subtask,
            feedback,
            git_repo,
        )

        # Assertions
        assert mock_session.called, "run_claude_session should have been called"
        assert mock_session.call_count == 1, "Should be called exactly once"

        # Verify the call arguments
        call_args = mock_session.call_args

        # First positional argument should be the prompt
        prompt = call_args[0][0]
        assert isinstance(prompt, str), "First argument should be prompt string"

        # Verify prompt contains feedback
        assert feedback in prompt, "Prompt should contain reviewer feedback"
        assert "Fix review issues" in prompt, "Prompt should contain fix description"
        assert sample_subtask.id in prompt, "Prompt should contain subtask ID"

        # Second positional argument should be project_dir
        project_dir_arg = call_args[0][1]
        assert project_dir_arg == git_repo, "Project directory should be passed correctly"

        # Third positional argument should be timeout
        timeout_arg = call_args[0][2]
        assert timeout_arg == test_config_with_review.orchestrator.session_timeout_seconds, (
            "Session timeout should be passed correctly"
        )

        # Keyword arguments should include debug_log_dir
        assert "debug_log_dir" in call_args[1], "debug_log_dir should be passed"
        debug_log_dir = call_args[1]["debug_log_dir"]
        expected_debug_dir = git_repo / ".rasen" / "debug_logs"
        assert debug_log_dir == expected_debug_dir, "Debug log directory should be correct"


def test_coder_fix_session_with_no_feedback(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test _run_coder_fix_session handles None feedback gracefully.

    This tests the coder fix session when feedback is None.
    It verifies:
    - run_claude_session is still called
    - Prompt contains "See previous feedback" fallback message
    - Session completes successfully with None feedback
    """
    # Mock run_claude_session to simulate successful execution
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.session_id = "test-session-87654321"
        mock_session.return_value = mock_result

        # Run coder fix session with None feedback
        _run_coder_fix_session(
            test_config_with_review,
            sample_subtask,
            feedback=None,
            project_dir=git_repo,
        )

        # Assertions
        assert mock_session.called, "run_claude_session should have been called"

        # Verify prompt contains fallback message
        call_args = mock_session.call_args
        prompt = call_args[0][0]
        assert "See previous feedback" in prompt, (
            "Prompt should contain fallback message when feedback is None"
        )


def test_coder_fix_session_handles_session_error(
    test_config_with_review: Config,
    sample_subtask: Subtask,
    git_repo: Path,
) -> None:
    """Test _run_coder_fix_session handles SessionError properly.

    This tests the error handling in _run_coder_fix_session (line 218-220).
    It verifies:
    - When run_claude_session raises SessionError
    - _run_coder_fix_session catches it and logs error
    - Function re-raises SessionError (line 220) to propagate to caller

    This specifically tests lines 218-220 in review.py:
    - Line 218: Catch SessionError exception
    - Line 219: Log error about coder fix session failure
    - Line 220: Re-raise SessionError to caller
    """
    feedback = "Fix the formatting"

    # Mock run_claude_session to raise SessionError
    with patch("rasen.review.run_claude_session") as mock_session:
        mock_session.side_effect = SessionError("Mock coder session error")

        # Run coder fix session - should re-raise SessionError
        with pytest.raises(SessionError, match="Mock coder session error"):
            _run_coder_fix_session(
                test_config_with_review,
                sample_subtask,
                feedback,
                git_repo,
            )

        # Verify the session was called
        assert mock_session.called, "run_claude_session should have been called"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
