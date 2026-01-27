"""Tests for prompt rendering."""

from __future__ import annotations

from rasen.prompts import create_agent_prompt


def test_create_initializer_prompt():
    """Test creating initializer prompt from bundled templates."""
    prompt = create_agent_prompt(
        "initializer",
        task_description="Build a web app",
    )

    assert "Build a web app" in prompt
    assert "Task Initialization" in prompt or "Session 1" in prompt


def test_create_coder_prompt():
    """Test creating coder prompt from bundled templates."""
    prompt = create_agent_prompt(
        "coder",
        subtask_id="task-1",
        subtask_description="Implement auth",
        attempt_number="1",
        memory_context="",
        failed_approaches_section="",
    )

    assert "task-1" in prompt
    assert "Implement auth" in prompt


def test_create_reviewer_prompt():
    """Test creating reviewer prompt from bundled templates."""
    prompt = create_agent_prompt(
        "reviewer",
        subtask_id="task-1",
        subtask_description="Test subtask",
        git_diff="+ added line\n- removed line",
    )

    assert "added line" in prompt


def test_create_qa_prompt():
    """Test creating QA prompt from bundled templates."""
    prompt = create_agent_prompt(
        "qa",
        task_description="Test QA",
        implementation_plan="Plan summary",
        full_git_diff="diff content",
        test_results="All passed",
    )

    assert "Test QA" in prompt


def test_prompt_variables_replaced():
    """Test that required variables are replaced in bundled templates."""
    prompt = create_agent_prompt(
        "coder",
        subtask_id="test-id",
        subtask_description="test desc",
        attempt_number="5",
        memory_context="memory",
        failed_approaches_section="failed",
    )

    # Check that the variables we passed are present in the output
    assert "test-id" in prompt
    assert "test desc" in prompt
    assert "#5" in prompt

    # These specific variables should be replaced
    assert "{subtask_id}" not in prompt
    assert "{subtask_description}" not in prompt
    assert "{attempt_number}" not in prompt
