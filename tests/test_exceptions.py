"""Tests for RASEN exception classes."""

from __future__ import annotations

import pytest

from rasen.exceptions import (
    ConfigurationError,
    GitError,
    RasenError,
    SessionError,
    StallDetectedError,
    ValidationError,
)
from rasen.models import TerminationReason


def test_rasen_error_base():
    """Test base RasenError exception."""
    error = RasenError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_configuration_error():
    """Test ConfigurationError exception."""
    error = ConfigurationError("Invalid config")
    assert str(error) == "Invalid config"
    assert isinstance(error, RasenError)


def test_session_error():
    """Test SessionError exception."""
    error = SessionError("Session failed")
    assert str(error) == "Session failed"
    assert isinstance(error, RasenError)


def test_validation_error():
    """Test ValidationError exception."""
    error = ValidationError("Validation failed")
    assert str(error) == "Validation failed"
    assert isinstance(error, RasenError)


def test_git_error():
    """Test GitError exception."""
    error = GitError("Git operation failed")
    assert str(error) == "Git operation failed"
    assert isinstance(error, RasenError)


def test_stall_detected_error():
    """Test StallDetectedError with termination reason."""
    error = StallDetectedError("Stalled", TerminationReason.STALLED)
    assert str(error) == "Stalled"
    assert error.termination_reason == TerminationReason.STALLED
    assert isinstance(error, RasenError)


def test_stall_detected_error_consecutive_failures():
    """Test StallDetectedError for consecutive failures."""
    error = StallDetectedError("Too many failures", TerminationReason.CONSECUTIVE_FAILURES)
    assert error.termination_reason == TerminationReason.CONSECUTIVE_FAILURES


def test_exception_hierarchy():
    """Test exception hierarchy is correct."""
    # All custom exceptions should be RasenError
    assert issubclass(ConfigurationError, RasenError)
    assert issubclass(SessionError, RasenError)
    assert issubclass(ValidationError, RasenError)
    assert issubclass(GitError, RasenError)
    assert issubclass(StallDetectedError, RasenError)

    # RasenError should be Exception
    assert issubclass(RasenError, Exception)


def test_exception_can_be_caught_as_base():
    """Test that specific exceptions can be caught as RasenError."""
    with pytest.raises(RasenError):
        raise ConfigurationError("Test")

    with pytest.raises(RasenError):
        raise SessionError("Test")

    with pytest.raises(RasenError):
        raise ValidationError("Test")


def test_stall_error_stores_reason():
    """Test that StallDetectedError properly stores termination reason."""
    try:
        raise StallDetectedError("Test stall", TerminationReason.MAX_ITERATIONS)
    except StallDetectedError as e:
        assert e.termination_reason == TerminationReason.MAX_ITERATIONS
        assert str(e) == "Test stall"
