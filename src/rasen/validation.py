"""Backpressure validation for quality gates."""

from __future__ import annotations

from rasen.config import BackpressureConfig
from rasen.models import Event


def validate_completion(
    events: list[Event],
    backpressure_config: BackpressureConfig,
) -> bool:
    """Validate that completion event has required evidence.

    This implements backpressure - agent claiming "done" must prove it.

    Args:
        events: List of events from agent output
        backpressure_config: Configuration for what to require

    Returns:
        True if completion is valid with required evidence

    Examples:
        >>> events = [Event(topic="build.done", payload="tests: pass, lint: pass")]
        >>> config = BackpressureConfig(require_tests=True, require_lint=True)
        >>> validate_completion(events, config)
        True
    """
    # Find completion event
    completion_event = None
    for event in events:
        if event.topic in ("build.done", "init.done"):
            completion_event = event
            break

    if not completion_event:
        return False

    payload_lower = completion_event.payload.lower()

    # Check required evidence
    if backpressure_config.require_tests and (
        "tests: pass" not in payload_lower and "test pass" not in payload_lower
    ):
        return False

    if backpressure_config.require_lint and (
        "lint: pass" not in payload_lower and "lint pass" not in payload_lower
    ):
        return False

    return True


def extract_completion_summary(events: list[Event]) -> str | None:
    """Extract summary from completion event.

    Args:
        events: List of events from agent output

    Returns:
        Summary text from completion event, or None if no completion event
    """
    for event in events:
        if event.topic in ("build.done", "init.done"):
            return event.payload
    return None


def has_quality_evidence(payload: str) -> dict[str, bool]:
    """Parse quality evidence from event payload.

    Args:
        payload: Event payload text

    Returns:
        Dict with boolean flags for each quality gate
    """
    payload_lower = payload.lower()
    return {
        "tests_pass": "tests: pass" in payload_lower or "test pass" in payload_lower,
        "lint_pass": "lint: pass" in payload_lower or "lint pass" in payload_lower,
        "type_check_pass": "mypy: pass" in payload_lower or "type check: pass" in payload_lower,
    }
