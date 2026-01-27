"""Tests for prompt rendering."""

from __future__ import annotations

from rasen.prompts import create_agent_prompt


def test_create_initializer_prompt(tmp_path, prompts_dir):
    """Test creating initializer prompt."""
    # prompts_dir is tmp_path/prompts, but create_agent_prompt expects base dir
    prompt = create_agent_prompt(
        "initializer",
        tmp_path,  # Will look in tmp_path/prompts/initializer.md
        task_description="Build a web app",
    )

    assert "Build a web app" in prompt
    assert "Initializer" in prompt


def test_create_coder_prompt(tmp_path, prompts_dir):
    """Test creating coder prompt."""
    prompt = create_agent_prompt(
        "coder",
        tmp_path,
        subtask_id="task-1",
        subtask_description="Implement auth",
        attempt_number="1",
        memory_context="",
        failed_approaches_section="",
    )

    assert "task-1" in prompt
    assert "Implement auth" in prompt
    assert "Coder" in prompt


def test_create_reviewer_prompt(tmp_path, prompts_dir):
    """Test creating reviewer prompt."""
    prompt = create_agent_prompt(
        "reviewer",
        tmp_path,
        git_diff="+ added line\n- removed line",
    )

    assert "added line" in prompt
    assert "Reviewer" in prompt


def test_create_qa_prompt(tmp_path, prompts_dir):
    """Test creating QA prompt."""
    prompt = create_agent_prompt(
        "qa",
        tmp_path,
        task_description="Test QA",
    )

    assert "Test QA" in prompt
    assert "QA" in prompt


def test_prompt_variables_replaced(tmp_path, prompts_dir):
    """Test that all variables are replaced."""
    prompt = create_agent_prompt(
        "coder",
        tmp_path,
        subtask_id="test-id",
        subtask_description="test desc",
        attempt_number="5",
        memory_context="memory",
        failed_approaches_section="failed",
    )

    # No template variables should remain
    assert "{{" not in prompt
    assert "}}" not in prompt
