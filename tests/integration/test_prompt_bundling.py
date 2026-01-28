"""Integration test for prompt bundling in standalone binary.

This test verifies that:
1. Prompts are bundled with the rasen package (not loaded from user's project)
2. Binary works from any directory (not just project root)
3. Prompts can be loaded via importlib.resources

This test would have caught the bug where prompts were being loaded from
project_dir/prompts/ instead of being bundled with the package.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
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
from rasen.prompts import create_agent_prompt, get_template_path


def test_prompts_load_from_package_resources():
    """Test that prompts can be loaded from package resources."""
    # This should work regardless of current working directory
    # because prompts are bundled with the package

    template = get_template_path("prompts/initializer.md")
    assert template is not None

    # Should be able to read content
    if hasattr(template, "read_text"):
        content = template.read_text(encoding="utf-8")  # type: ignore[union-attr]
    else:
        content = Path(template).read_text(encoding="utf-8")

    assert "Task Initialization" in content or "RASEN" in content


def test_create_prompt_works_without_project_prompts_dir():
    """Test that create_agent_prompt works without a prompts/ directory in user's project."""
    # This is the key test - prompts should load from package, not user's project
    prompt = create_agent_prompt(
        "initializer",
        task_description="Test task",
    )

    assert "Test task" in prompt
    assert len(prompt) > 100  # Should have substantial content


def test_all_agent_prompts_are_bundled():
    """Test that all required agent prompts are bundled and accessible."""
    agent_types = ["initializer", "coder", "reviewer", "qa"]

    for agent_type in agent_types:
        # Should not raise ConfigurationError
        if agent_type == "initializer":
            prompt = create_agent_prompt(agent_type, task_description="Test")
        elif agent_type == "coder":
            prompt = create_agent_prompt(
                agent_type,
                subtask_id="test-1",
                subtask_description="Test",
                attempt_number="1",
                memory_context="",
                failed_approaches_section="",
            )
        elif agent_type == "reviewer":
            prompt = create_agent_prompt(
                agent_type,
                subtask_id="test-1",
                subtask_description="Test",
                git_diff="diff",
            )
        elif agent_type == "qa":
            prompt = create_agent_prompt(
                agent_type,
                task_description="Test",
                implementation_plan="Plan",
                full_git_diff="diff",
                test_results="passed",
            )

        assert len(prompt) > 50, f"{agent_type} prompt is too short or empty"


@pytest.mark.integration
def test_orchestration_from_directory_without_prompts(tmp_path: Path):
    """Test orchestration from a directory that DOES NOT contain prompts/.

    This simulates a real user's project directory, which should NOT contain
    the rasen prompt templates. Prompts must be bundled with the package.

    This test would have caught the original bug where code tried to load
    prompts from {project_dir}/prompts/initializer.md.
    """
    # Create a test project WITHOUT prompts/ directory
    project_dir = tmp_path / "user-project"
    project_dir.mkdir()

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    # Initial commit
    (project_dir / "README.md").write_text("# User Project")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    # CRITICAL: Verify no prompts/ directory in user's project
    assert not (project_dir / "prompts").exists(), (
        "Test setup error: prompts/ should NOT exist in user's project"
    )

    # Create config pointing to user's project (no prompts there)
    rasen_dir = project_dir / ".rasen"
    rasen_dir.mkdir()

    config = Config(
        project=ProjectConfig(
            name="user-project",
            root=str(project_dir),
        ),
        orchestrator=OrchestratorConfig(
            max_iterations=1,
            session_delay_seconds=0,
        ),
        agent=AgentConfig(model="claude-sonnet-4-20250514"),
        worktree=WorktreeConfig(enabled=False),
        memory=MemoryConfig(enabled=False, path=str(rasen_dir / "memories.md")),
        backpressure=BackpressureConfig(require_tests=False, require_lint=False),
        background=BackgroundConfig(
            enabled=False,
            pid_file=str(rasen_dir / "rasen.pid"),
            log_file=str(rasen_dir / "rasen.log"),
            status_file=str(rasen_dir / "status.json"),
        ),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=2,
            max_consecutive_failures=3,
        ),
        review=ReviewConfig(enabled=False),
        qa=QAConfig(enabled=False),
    )

    # Mock Claude session to simulate Initializer creating plan
    def mock_initializer_creates_plan(*_args, **_kwargs):
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
        plan_file = rasen_dir / "state.json"
        plan_file.write_text(json.dumps(plan, indent=2))

        result = MagicMock()
        result.returncode = 0
        return result

    with patch("rasen.loop.run_claude_session", side_effect=mock_initializer_creates_plan):
        # Run orchestration from user's project (WITHOUT prompts/)
        loop = OrchestrationLoop(config, project_dir, "Test task")

        try:
            loop.run()
        except Exception as e:
            # If we get ConfigurationError about prompts not found, the bug exists
            if "Prompt template not found" in str(e):
                pytest.fail(
                    f"BUG: Tried to load prompts from user's project directory! "
                    f"Prompts should be bundled with the package. Error: {e}"
                )
            # Other errors are OK for this test (we just care about prompt loading)

    # NOTE: Prompts are now passed directly to Claude, not written to .rasen/
    # The orchestration ran successfully without FileNotFoundError, which proves
    # that prompts were loaded from the bundled package resources

    # Verify plan was created (means orchestration actually ran)
    plan_file = rasen_dir / "state.json"
    assert plan_file.exists(), "Plan should have been created by Initializer"


@pytest.mark.integration
def test_binary_works_from_any_directory():
    """Test that the standalone binary works from any directory.

    This is the ultimate integration test - run the actual binary from
    a random directory that doesn't contain prompts.
    """
    binary_path = Path(__file__).parent.parent.parent / "dist" / "rasen"

    if not binary_path.exists():
        pytest.skip("Binary not built. Run 'python build.py' first.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Initialize a new project in random temp directory
        result = subprocess.run(
            [str(binary_path), "init", "--task", "test task"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

        # Should succeed (not fail with "Prompt template not found")
        assert result.returncode == 0, (
            f"Binary failed from temp directory. This means prompts aren't bundled!\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        assert "Task initialized" in result.stdout or "✅" in result.stdout

        # Verify .rasen directory was created
        assert (tmp_path / ".rasen").exists()
        assert (tmp_path / ".rasen" / "task.txt").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
