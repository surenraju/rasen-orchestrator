"""Tests for recovery store."""

from __future__ import annotations

from rasen.stores.recovery_store import RecoveryStore


def test_get_recovery_hints_first_attempt(rasen_dir):
    """Test recovery hints for first attempt."""
    store = RecoveryStore(rasen_dir)

    hints = store.get_recovery_hints("task-1")

    assert len(hints) == 1
    assert hints[0] == "This is the first attempt at this subtask"


def test_get_recovery_hints_single_attempt(rasen_dir):
    """Test recovery hints after one attempt."""
    store = RecoveryStore(rasen_dir)

    # Record one failed attempt
    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="Try using async/await pattern",
    )

    hints = store.get_recovery_hints("task-1")

    # Should show attempt count and the single attempt
    assert "Previous attempts: 1" in hints[0]
    assert any("Attempt 1: Try using async/await pattern - FAILED" in h for h in hints)
    # Should not show warning yet (only 1 attempt)
    assert not any("IMPORTANT" in h for h in hints)


def test_get_recovery_hints_multiple_attempts(rasen_dir):
    """Test recovery hints after multiple attempts."""
    store = RecoveryStore(rasen_dir)

    # Record multiple attempts
    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="Try using async/await pattern",
    )
    store.record_attempt(
        subtask_id="task-1",
        session=2,
        success=False,
        approach="Try using callbacks instead",
    )

    hints = store.get_recovery_hints("task-1")

    # Should show attempt count
    assert "Previous attempts: 2" in hints[0]

    # Should show both attempts
    assert any("Attempt 1: Try using async/await pattern - FAILED" in h for h in hints)
    assert any("Attempt 2: Try using callbacks instead - FAILED" in h for h in hints)

    # Should show warning (2+ attempts)
    assert any("IMPORTANT: Try a DIFFERENT approach" in h for h in hints)
    assert any("Consider: different library" in h for h in hints)


def test_get_recovery_hints_success_and_failure(rasen_dir):
    """Test recovery hints with mix of success and failure."""
    store = RecoveryStore(rasen_dir)

    # Record mixed attempts
    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="First approach failed",
    )
    store.record_attempt(
        subtask_id="task-1",
        session=2,
        success=True,
        approach="Second approach worked",
        commit_hash="abc123",
    )

    hints = store.get_recovery_hints("task-1")

    # Should show both attempts with correct status
    assert any("Attempt 1: First approach failed - FAILED" in h for h in hints)
    assert any("Attempt 2: Second approach worked - SUCCESS" in h for h in hints)


def test_get_recovery_hints_shows_last_three(rasen_dir):
    """Test recovery hints only shows last 3 attempts."""
    store = RecoveryStore(rasen_dir)

    # Record 5 attempts
    for i in range(1, 6):
        store.record_attempt(
            subtask_id="task-1",
            session=i,
            success=False,
            approach=f"Approach {i}",
        )

    hints = store.get_recovery_hints("task-1")

    # Should show total count
    assert "Previous attempts: 5" in hints[0]

    # Should only show last 3 attempts
    assert any("Attempt 1: Approach 3 - FAILED" in h for h in hints)
    assert any("Attempt 2: Approach 4 - FAILED" in h for h in hints)
    assert any("Attempt 3: Approach 5 - FAILED" in h for h in hints)

    # Should NOT show first two attempts
    assert not any("Approach 1" in h for h in hints)
    assert not any("Approach 2" in h for h in hints)


def test_get_recovery_hints_different_subtasks(rasen_dir):
    """Test recovery hints are isolated per subtask."""
    store = RecoveryStore(rasen_dir)

    # Record attempts for different subtasks
    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="Task 1 approach",
    )
    store.record_attempt(
        subtask_id="task-2",
        session=2,
        success=False,
        approach="Task 2 approach",
    )

    # Get hints for task-1
    hints_1 = store.get_recovery_hints("task-1")
    # Get hints for task-2
    hints_2 = store.get_recovery_hints("task-2")

    # Each should only show their own attempts
    assert any("Task 1 approach" in h for h in hints_1)
    assert not any("Task 2 approach" in h for h in hints_1)

    assert any("Task 2 approach" in h for h in hints_2)
    assert not any("Task 1 approach" in h for h in hints_2)


def test_record_attempt_creates_history(rasen_dir):
    """Test recording attempt creates history file."""
    store = RecoveryStore(rasen_dir)

    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=True,
        approach="Initial implementation",
        commit_hash="abc123",
    )

    # Verify file was created and can be read
    assert store.history_path.exists()

    # Verify we can get the attempt back
    history = store._load_history()
    assert len(history.records) == 1
    assert history.records[0].subtask_id == "task-1"
    assert history.records[0].approach == "Initial implementation"
    assert history.records[0].success is True


def test_get_failed_approaches(rasen_dir):
    """Test getting only failed approaches."""
    store = RecoveryStore(rasen_dir)

    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="Failed approach 1",
    )
    store.record_attempt(
        subtask_id="task-1",
        session=2,
        success=True,
        approach="Successful approach",
        commit_hash="abc123",
    )
    store.record_attempt(
        subtask_id="task-1",
        session=3,
        success=False,
        approach="Failed approach 2",
    )

    failed = store.get_failed_approaches("task-1")

    assert len(failed) == 2
    assert "Failed approach 1" in failed
    assert "Failed approach 2" in failed
    assert "Successful approach" not in failed


def test_get_attempt_count(rasen_dir):
    """Test getting total attempt count."""
    store = RecoveryStore(rasen_dir)

    # Initially zero
    assert store.get_attempt_count("task-1") == 0

    # After recording attempts
    store.record_attempt(subtask_id="task-1", session=1, success=False, approach="Attempt 1")
    assert store.get_attempt_count("task-1") == 1

    store.record_attempt(subtask_id="task-1", session=2, success=True, approach="Attempt 2")
    assert store.get_attempt_count("task-1") == 2

    # Different subtask should be independent
    assert store.get_attempt_count("task-2") == 0


def test_is_thrashing_detects_consecutive_failures(rasen_dir):
    """Test thrashing detection with consecutive failures."""
    store = RecoveryStore(rasen_dir)

    # Record 3 consecutive failures
    for i in range(1, 4):
        store.record_attempt(subtask_id="task-1", session=i, success=False, approach=f"Attempt {i}")

    # Should detect thrashing after 3 failures
    assert store.is_thrashing("task-1", threshold=3)


def test_is_thrashing_not_detected_with_success(rasen_dir):
    """Test thrashing not detected when there's a success."""
    store = RecoveryStore(rasen_dir)

    # Record 2 failures, then success
    store.record_attempt(subtask_id="task-1", session=1, success=False, approach="Attempt 1")
    store.record_attempt(subtask_id="task-1", session=2, success=False, approach="Attempt 2")
    store.record_attempt(subtask_id="task-1", session=3, success=True, approach="Attempt 3")

    # Should NOT detect thrashing (last attempt was success)
    assert not store.is_thrashing("task-1", threshold=3)


def test_good_commit_tracking(rasen_dir):
    """Test recording and retrieving good commits."""
    store = RecoveryStore(rasen_dir)

    # Initially no commits
    assert store.get_last_good_commit() is None

    # Record a good commit
    store.record_good_commit(commit_hash="abc123", subtask_id="task-1")
    assert store.get_last_good_commit() == "abc123"

    # Record another commit
    store.record_good_commit(commit_hash="def456", subtask_id="task-2")
    assert store.get_last_good_commit() == "def456"  # Returns most recent


def test_record_attempt_with_error_message(rasen_dir):
    """Test recording attempt with error message."""
    store = RecoveryStore(rasen_dir)

    # Record failed attempt with error
    error_msg = "TypeError: expected string, got int"
    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=False,
        approach="Try using type hints",
        error_message=error_msg,
    )

    # Verify error message is stored
    history = store._load_history()
    assert len(history.records) == 1
    assert history.records[0].error_message == error_msg
    assert history.records[0].success is False


def test_record_attempt_with_commit_hash(rasen_dir):
    """Test recording successful attempt with commit hash."""
    store = RecoveryStore(rasen_dir)

    # Record successful attempt with commit
    store.record_attempt(
        subtask_id="task-1",
        session=1,
        success=True,
        approach="Implemented using dataclasses",
        commit_hash="abc123def456",
    )

    # Verify commit hash is stored
    history = store._load_history()
    assert len(history.records) == 1
    assert history.records[0].commit_hash == "abc123def456"
    assert history.records[0].success is True
    assert history.records[0].error_message is None  # No error for success
