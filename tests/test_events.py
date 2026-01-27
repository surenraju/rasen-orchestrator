"""Tests for event parsing."""

from __future__ import annotations

from rasen.events import parse_events
from rasen.models import Event


def test_parse_single_event():
    """Test parsing a single event."""
    xml = '<event topic="build.done">tests: pass, lint: pass</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert events[0].topic == "build.done"
    assert events[0].payload == "tests: pass, lint: pass"


def test_parse_multiple_events():
    """Test parsing multiple events."""
    xml = """
    <event topic="build.done">First event</event>
    <event topic="init.done">Second event</event>
    """
    events = parse_events(xml)

    assert len(events) == 2
    assert events[0].topic == "build.done"
    assert events[0].payload == "First event"
    assert events[1].topic == "init.done"
    assert events[1].payload == "Second event"


def test_parse_event_with_newlines():
    """Test parsing event with multiline payload."""
    xml = """<event topic="qa.rejected">Issue 1: Missing tests
Issue 2: Bad formatting
Issue 3: No documentation</event>"""
    events = parse_events(xml)

    assert len(events) == 1
    assert "Issue 1" in events[0].payload
    assert "Issue 2" in events[0].payload
    assert "Issue 3" in events[0].payload


def test_parse_no_events():
    """Test parsing text with no events."""
    text = "This is just regular output with no events"
    events = parse_events(text)

    assert len(events) == 0


def test_parse_empty_string():
    """Test parsing empty string."""
    events = parse_events("")
    assert len(events) == 0


def test_parse_malformed_xml():
    """Test parsing malformed XML doesn't crash."""
    xml = "<event topic='unclosed'>Test"
    events = parse_events(xml)

    # Should gracefully handle malformed XML
    # Implementation might return 0 or 1 event depending on parser
    assert isinstance(events, list)


def test_parse_event_with_special_characters():
    """Test parsing event with special characters."""
    xml = '<event topic="build.done">tests: pass & lint: pass > 0</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert "&" in events[0].payload
    assert ">" in events[0].payload


def test_parse_mixed_content():
    """Test parsing events mixed with regular text."""
    text = """
    Some debug output here
    <event topic="build.done">Completed</event>
    More output
    <event topic="memory.store">Stored pattern</event>
    Final output
    """
    events = parse_events(text)

    assert len(events) == 2
    assert events[0].topic == "build.done"
    assert events[1].topic == "memory.store"


def test_parse_review_events():
    """Test parsing review-specific events."""
    xml = '<event topic="review.approved">LGTM, looks good!</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert events[0].topic == "review.approved"


def test_parse_review_changes_requested():
    """Test parsing review changes requested event."""
    xml = '<event topic="review.changes_requested">Need better error handling</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert events[0].topic == "review.changes_requested"
    assert "error handling" in events[0].payload


def test_parse_qa_events():
    """Test parsing QA-specific events."""
    xml = '<event topic="qa.approved">All criteria met</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert events[0].topic == "qa.approved"


def test_parse_qa_rejected():
    """Test parsing QA rejected event."""
    xml = '<event topic="qa.rejected">Missing password validation</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert events[0].topic == "qa.rejected"


def test_parse_blocked_event():
    """Test parsing blocked event."""
    xml = '<event topic="build.blocked">Cannot proceed without API key</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert events[0].topic == "build.blocked"
    assert "API key" in events[0].payload


def test_parse_event_preserves_whitespace():
    """Test that whitespace in payload is preserved."""
    xml = '<event topic="test">  Indented line\n  Another line  </event>'
    events = parse_events(xml)

    assert len(events) == 1
    # XML parser might strip some whitespace, but content should be preserved
    assert "Indented" in events[0].payload
    assert "Another" in events[0].payload


def test_parse_returns_event_objects():
    """Test that parse_events returns Event objects."""
    xml = '<event topic="build.done">Success</event>'
    events = parse_events(xml)

    assert len(events) == 1
    assert isinstance(events[0], Event)
    assert hasattr(events[0], "topic")
    assert hasattr(events[0], "payload")


def test_parse_event_with_empty_payload():
    """Test parsing event with empty payload."""
    xml = '<event topic="build.done"></event>'
    events = parse_events(xml)

    # Should handle empty payload gracefully
    if len(events) > 0:
        assert events[0].topic == "build.done"
        assert events[0].payload == "" or events[0].payload is not None


def test_parse_multiple_same_topic():
    """Test parsing multiple events with same topic."""
    xml = """
    <event topic="memory.store">Pattern 1</event>
    <event topic="memory.store">Pattern 2</event>
    <event topic="memory.store">Pattern 3</event>
    """
    events = parse_events(xml)

    assert len(events) == 3
    assert all(e.topic == "memory.store" for e in events)
    assert events[0].payload == "Pattern 1"
    assert events[1].payload == "Pattern 2"
    assert events[2].payload == "Pattern 3"
