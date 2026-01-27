"""RASEN exception hierarchy."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rasen.models import TerminationReason


class RasenError(Exception):
    """Base exception for all RASEN errors."""


class ConfigurationError(RasenError):
    """Invalid or missing configuration."""


class SessionError(RasenError):
    """Error during agent session execution."""


class SessionTimeoutError(SessionError):
    """Session exceeded time limit."""


class IdleTimeoutError(SessionError):
    """Session idle (no output) for too long."""


class ValidationError(RasenError):
    """Validation failed (backpressure, state, etc.)."""


class GitError(RasenError):
    """Git operation failed."""


class StoreError(RasenError):
    """State store operation failed."""


class StallDetectedError(RasenError):
    """Stall condition detected, aborting."""

    def __init__(self, reason: str, termination_reason: TerminationReason) -> None:
        super().__init__(reason)
        self.termination_reason = termination_reason
