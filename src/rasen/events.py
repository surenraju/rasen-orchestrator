"""Event parsing from agent output."""

from __future__ import annotations

import re

from rasen.models import Event


def parse_events(output: str) -> list[Event]:
    """Extract <event> tags from agent output.

    Args:
        output: Raw agent output text.

    Returns:
        List of Event objects extracted from output.
    """
    events: list[Event] = []
    pattern = r'<event\s+topic="([^"]+)">(.*?)</event>'

    for match in re.finditer(pattern, output, re.DOTALL):
        topic = match.group(1).strip()
        payload = match.group(2).strip()
        events.append(Event(topic=topic, payload=payload))

    return events


def has_completion_event(events: list[Event]) -> bool:
    """Check if events contain a completion signal.

    Args:
        events: List of Event objects

    Returns:
        True if any event is a completion signal
    """
    completion_topics = {"build.done", "init.done"}
    return any(e.topic in completion_topics for e in events)


def has_blocked_event(events: list[Event]) -> bool:
    """Check if events contain a blocked signal.

    Args:
        events: List of Event objects

    Returns:
        True if any event is a blocked signal
    """
    return any(e.topic == "build.blocked" for e in events)


def get_event_payload(events: list[Event], topic: str) -> str | None:
    """Get payload for a specific event topic.

    Args:
        events: List of Event objects
        topic: Event topic to search for

    Returns:
        Payload of first matching event, or None if not found
    """
    for event in events:
        if event.topic == topic:
            return event.payload
    return None
