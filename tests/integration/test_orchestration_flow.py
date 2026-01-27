"""Integration test for orchestration flow.

This test would have caught both critical bugs:
1. Initializer agent not being called
2. Prompt template path doubled (prompts/prompts/...)

These bugs were missed because:
- Unit tests don't test the full loop
- Integration tests didn't actually run the orchestrator
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
from rasen.loop import OrchestrationLoop


@pytest.fixture
def mock_claude_session():
    """Mock Claude Code CLI session."""
    with patch("rasen.loop.run_claude_session") as mock:
        # Simulate successful session
        result = MagicMock()
        result.returncode = 0
        mock.return_value = result
        yield mock


@pytest.fixture
def test_project_with_prompts(tmp_path: Path) -> Path:
    """Create test project with prompt templates."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # Create prompts directory with templates
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir()

    # Create prompt templates
    (prompts_dir / "initializer.md").write_text("""
# Initializer Prompt

Task: {task_description}

Create implementation plan and save to `.rasen/implementation_plan.json`.
    """)

    (prompts_dir / "coder.md").write_text("""
# Coder Prompt

Subtask: {subtask_id}
Description: {subtask_description}
Attempt: {attempt_number}

Memory: {memory_context}
Failed Approaches: {failed_approaches_section}
    """)

    (prompts_dir / "reviewer.md").write_text("""
# Reviewer Prompt

Subtask: {subtask_id}
Description: {subtask_description}

Diff:
{git_diff}
    """)

    (prompts_dir / "qa.md").write_text("""
# QA Prompt

Task: {task_description}
Plan: {implementation_plan}
Diff: {full_git_diff}
Tests: {test_results}
    """)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=project_dir, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    # Initial commit
    (project_dir / "README.md").write_text("# Test Project")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    return project_dir


@pytest.fixture
def test_config(test_project_with_prompts: Path) -> Config:
    """Create test configuration."""
    return Config(
        project=ProjectConfig(
            name="test-project",
            root=str(test_project_with_prompts),
        ),
        orchestrator=OrchestratorConfig(
            max_iterations=3,
            session_delay_seconds=0,
        ),
        agent=AgentConfig(
            model="claude-sonnet-4-20250514",
        ),
        worktree=WorktreeConfig(enabled=False),
        memory=MemoryConfig(
            enabled=False,
            path=str(test_project_with_prompts / ".rasen" / "memories.md"),
        ),
        backpressure=BackpressureConfig(
            require_tests=False,
            require_lint=False,
        ),
        background=BackgroundConfig(
            enabled=False,
            pid_file=str(test_project_with_prompts / ".rasen" / "rasen.pid"),
            log_file=str(test_project_with_prompts / ".rasen" / "rasen.log"),
            status_file=str(test_project_with_prompts / ".rasen" / "status.json"),
        ),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=2,
            max_consecutive_failures=3,
        ),
        review=ReviewConfig(enabled=False),
        qa=QAConfig(enabled=False),
    )


def test_initializer_is_called_when_no_plan(
    test_config: Config,
    test_project_with_prompts: Path,
    mock_claude_session: MagicMock,
) -> None:
    """Test that Initializer agent is called when no plan exists.

    This test catches BUG #1: Initializer not being called.

    Expected behavior:
    1. Loop starts with no plan
    2. Detects no plan exists
    3. Calls _run_initializer_session()
    4. Creates implementation_plan.json

    Bug that was missed:
    - Loop assumed plan existed
    - get_next_subtask() returned None
    - Interpreted as "all subtasks complete"
    - Exited immediately without calling Initializer
    """
    # Setup: No plan exists
    rasen_dir = test_project_with_prompts / ".rasen"
    rasen_dir.mkdir(exist_ok=True)

    # Create minimal plan that Initializer would create
    def mock_initializer_creates_plan(*_args, **_kwargs):
        # Simulate Initializer creating a plan
        plan = {
            "task_name": "Test task",
            "subtasks": [
                {
                    "id": "task-1",
                    "description": "First task",
                    "status": "pending",
                    "attempts": 0,
                    "last_approach": None,
                }
            ],
        }
        plan_file = rasen_dir / "implementation_plan.json"
        plan_file.write_text(json.dumps(plan, indent=2))

        result = MagicMock()
        result.returncode = 0
        return result

    mock_claude_session.side_effect = mock_initializer_creates_plan

    # Run orchestration loop
    loop = OrchestrationLoop(test_config, test_project_with_prompts, "Test task")

    with contextlib.suppress(Exception):
        # May fail on subsequent sessions, we just care about init
        loop.run()

    # ASSERTION: Initializer was called
    assert mock_claude_session.called, "Initializer session was never called!"

    # ASSERTION: Plan was created
    plan_file = rasen_dir / "implementation_plan.json"
    assert plan_file.exists(), "implementation_plan.json was not created!"

    # NOTE: Prompts are passed directly to Claude, not written to disk


def test_prompt_paths_are_correct(
    test_config: Config,
    test_project_with_prompts: Path,
    mock_claude_session: MagicMock,
) -> None:
    """Test that prompt template paths are constructed correctly.

    This test catches BUG #2: Double prompts path (prompts/prompts/).

    Expected behavior:
    - AGENT_CONFIGS has "prompts/initializer.md"
    - Pass project_dir as base
    - Result: project_dir / "prompts/initializer.md" ✓

    Bug that was missed:
    - Pass Path("prompts") as base
    - Result: prompts / prompts/initializer.md ✗
    - Error: "Prompt template not found: prompts/prompts/initializer.md"
    """
    # Setup: No plan exists so Initializer runs
    rasen_dir = test_project_with_prompts / ".rasen"
    rasen_dir.mkdir(exist_ok=True)

    prompt_content = None

    def capture_prompt(prompt, *_args, **_kwargs):
        nonlocal prompt_content
        prompt_content = prompt

        # Create plan after Initializer
        plan = {
            "task_name": "Test",
            "subtasks": [{"id": "t1", "description": "Task", "status": "pending", "attempts": 0}],
        }
        (rasen_dir / "implementation_plan.json").write_text(json.dumps(plan))

        result = MagicMock()
        result.returncode = 0
        return result

    mock_claude_session.side_effect = capture_prompt

    # Run loop
    loop = OrchestrationLoop(test_config, test_project_with_prompts, "Test")
    with contextlib.suppress(Exception):
        loop.run()

    # ASSERTION: Prompt string was passed to Claude session
    assert prompt_content is not None, "No prompt was passed to Claude session!"
    assert isinstance(prompt_content, str), "Prompt should be a string!"
    assert len(prompt_content) > 0, "Prompt should not be empty!"


def test_prompt_templates_exist_before_running(test_project_with_prompts: Path) -> None:
    """Test that all required prompt templates exist.

    This is a basic sanity check that would catch deployment issues.
    """
    prompts_dir = test_project_with_prompts / "prompts"

    required_templates = [
        "initializer.md",
        "coder.md",
        "reviewer.md",
        "qa.md",
    ]

    for template in required_templates:
        template_path = prompts_dir / template
        assert template_path.exists(), f"Missing prompt template: {template}"
        assert template_path.stat().st_size > 0, f"Empty prompt template: {template}"


@pytest.mark.skip(reason="Expensive test - requires full orchestration with Claude API")
def test_full_orchestration_flow_with_api(
    test_config: Config, test_project_with_prompts: Path
) -> None:
    """Full integration test with real Claude API.

    This test actually calls Claude and verifies the complete flow:
    1. Initializer creates plan
    2. Coder implements subtasks
    3. Git commits are made
    4. Files are created

    NOTE: This is the GOLD STANDARD test that would have caught both bugs.
    It's skipped by default due to cost/time but should be run before releases.
    """
    # Enable full config
    test_config.backpressure.require_tests = False  # Don't require tests for simple task
    test_config.backpressure.require_lint = False

    # Run orchestration
    loop = OrchestrationLoop(
        test_config, test_project_with_prompts, "Create a simple hello.py file"
    )
    result = loop.run()

    # Verify plan was created
    plan_file = test_project_with_prompts / ".rasen" / "implementation_plan.json"
    assert plan_file.exists()

    # Verify file was created
    hello_file = test_project_with_prompts / "hello.py"
    assert hello_file.exists()

    # Verify git commit was made
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=test_project_with_prompts,
        capture_output=True,
        text=True,
        check=False,
    )
    # Should have initial commit + at least one implementation commit
    assert len(result.stdout.strip().split("\n")) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
