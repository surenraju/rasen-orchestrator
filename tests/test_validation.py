"""Tests for backpressure validation."""

from __future__ import annotations

from rasen.config import BackpressureConfig
from rasen.models import Event
from rasen.validation import validate_completion


def test_validate_completion_with_tests_and_lint():
    """Test validation passes with tests and lint evidence."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.done", payload="tests: pass, lint: pass")]

    assert validate_completion(events, config) is True


def test_validate_completion_missing_tests():
    """Test validation fails when tests not mentioned."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.done", payload="lint: pass")]

    assert validate_completion(events, config) is False


def test_validate_completion_missing_lint():
    """Test validation fails when lint not mentioned."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.done", payload="tests: pass")]

    assert validate_completion(events, config) is False


def test_validate_completion_no_build_done_event():
    """Test validation fails with no completion event."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="memory.store", payload="tests: pass, lint: pass")]

    assert validate_completion(events, config) is False


def test_validate_completion_empty_events():
    """Test validation fails with no events."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events: list[Event] = []

    assert validate_completion(events, config) is False


def test_validate_completion_only_tests_required():
    """Test validation with only tests required."""
    config = BackpressureConfig(require_tests=True, require_lint=False)
    events = [Event(topic="build.done", payload="tests: pass")]

    assert validate_completion(events, config) is True


def test_validate_completion_only_lint_required():
    """Test validation with only lint required."""
    config = BackpressureConfig(require_tests=False, require_lint=True)
    events = [Event(topic="build.done", payload="lint: pass")]

    assert validate_completion(events, config) is True


def test_validate_completion_nothing_required():
    """Test validation with no requirements."""
    config = BackpressureConfig(require_tests=False, require_lint=False)
    events = [Event(topic="build.done", payload="anything")]

    assert validate_completion(events, config) is True


def test_validate_completion_case_insensitive():
    """Test validation is case insensitive."""
    config = BackpressureConfig(require_tests=True, require_lint=True)

    # Uppercase
    events1 = [Event(topic="build.done", payload="TESTS: PASS, LINT: PASS")]
    assert validate_completion(events1, config) is True

    # Mixed case
    events2 = [Event(topic="build.done", payload="Tests: Pass, Lint: Pass")]
    assert validate_completion(events2, config) is True


def test_validate_completion_init_done_event():
    """Test validation works with init.done event."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="init.done", payload="tests: pass, lint: pass")]

    assert validate_completion(events, config) is True


def test_validate_completion_multiple_events():
    """Test validation checks only completion events."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [
        Event(topic="memory.store", payload="some memory"),
        Event(topic="build.done", payload="tests: pass, lint: pass"),
        Event(topic="debug", payload="debug info"),
    ]

    assert validate_completion(events, config) is True


def test_validate_completion_first_build_done_wins():
    """Test validation uses first build.done event."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [
        Event(topic="build.done", payload="tests: pass, lint: pass"),
        Event(topic="build.done", payload="different payload"),
    ]

    assert validate_completion(events, config) is True


def test_validate_completion_tests_failed():
    """Test validation fails when tests fail."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.done", payload="tests: fail, lint: pass")]

    assert validate_completion(events, config) is False


def test_validate_completion_lint_failed():
    """Test validation fails when lint fails."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.done", payload="tests: pass, lint: fail")]

    assert validate_completion(events, config) is False


def test_validate_completion_verbose_payload():
    """Test validation with verbose payload."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    payload = """
    I have completed the task successfully.
    All tests: pass (15 tests executed)
    Lint: pass (0 errors, 0 warnings)
    Ready for review.
    """
    events = [Event(topic="build.done", payload=payload)]

    assert validate_completion(events, config) is True


def test_validate_completion_minimal_payload():
    """Test validation with minimal payload."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    # Validation requires "tests: pass" or "test pass"
    events = [Event(topic="build.done", payload="test pass lint pass")]

    assert validate_completion(events, config) is True


def test_validate_completion_with_extra_text():
    """Test validation with evidence buried in text."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [
        Event(
            topic="build.done",
            payload="Implemented feature X. Ran tests: pass. Ran lint: pass. All done!",
        )
    ]

    assert validate_completion(events, config) is True


def test_validate_completion_blocked_event():
    """Test validation fails for blocked event."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.blocked", payload="tests: pass, lint: pass")]

    assert validate_completion(events, config) is False


def test_validate_completion_with_numbers():
    """Test validation with test counts."""
    config = BackpressureConfig(require_tests=True, require_lint=True)
    events = [Event(topic="build.done", payload="tests: pass (12/12), lint: pass")]

    assert validate_completion(events, config) is True
