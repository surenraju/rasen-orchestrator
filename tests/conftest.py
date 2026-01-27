"""Pytest fixtures for RASEN tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

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
)
from rasen.models import (
    ImplementationPlan,
    Subtask,
    SubtaskStatus,
)


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


@pytest.fixture
def rasen_dir(temp_project_dir: Path) -> Path:
    """Create .rasen directory for state files."""
    rasen = temp_project_dir / ".rasen"
    rasen.mkdir(parents=True, exist_ok=True)
    return rasen


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    """Create prompts directory with template files."""
    prompts = tmp_path / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)

    # Create minimal template files
    (prompts / "initializer.md").write_text("# Initializer\n{{task_description}}")
    (prompts / "coder.md").write_text("# Coder\n{{subtask_id}}\n{{subtask_description}}")
    (prompts / "reviewer.md").write_text("# Reviewer\n{{git_diff}}")
    (prompts / "qa.md").write_text("# QA\n{{task_description}}")

    return prompts


@pytest.fixture
def test_config(temp_project_dir: Path, rasen_dir: Path) -> Config:
    """Create a test configuration."""
    return Config(
        project=ProjectConfig(
            name="test-project",
            root=str(temp_project_dir),
        ),
        orchestrator=OrchestratorConfig(
            max_iterations=10,
            max_runtime_seconds=300,
            session_delay_seconds=0,  # No delay in tests
            session_timeout_seconds=60,
            idle_timeout_seconds=30,
        ),
        agent=AgentConfig(
            model="claude-sonnet-4-20250514",
            max_thinking_tokens=4096,
        ),
        memory=MemoryConfig(
            enabled=True,
            path=str(rasen_dir / "memories.md"),
            max_tokens=1000,
        ),
        backpressure=BackpressureConfig(
            require_tests=True,
            require_lint=True,
        ),
        stall_detection=StallDetectionConfig(
            max_no_commit_sessions=3,
            max_consecutive_failures=5,
        ),
        background=BackgroundConfig(
            status_file=str(rasen_dir / "status.json"),
            pid_file=str(rasen_dir / "rasen.pid"),
            log_file=str(rasen_dir / "rasen.log"),
        ),
        review=ReviewConfig(
            enabled=True,
            max_loops=3,
        ),
        qa=QAConfig(
            enabled=True,
            max_iterations=10,
            recurring_issue_threshold=3,
        ),
    )


@pytest.fixture
def sample_plan() -> ImplementationPlan:
    """Create a sample implementation plan."""
    return ImplementationPlan(
        task_name="Test task",
        subtasks=[
            Subtask(
                id="task-1",
                description="First subtask",
                status=SubtaskStatus.PENDING,
            ),
            Subtask(
                id="task-2",
                description="Second subtask",
                status=SubtaskStatus.PENDING,
            ),
            Subtask(
                id="task-3",
                description="Third subtask",
                status=SubtaskStatus.PENDING,
            ),
        ],
    )


@pytest.fixture
def git_repo(temp_project_dir: Path) -> Path:
    """Create a git repository for testing."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_project_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_project_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = temp_project_dir / "README.md"
    readme.write_text("# Test Project\n")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=temp_project_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_project_dir,
        check=True,
        capture_output=True,
    )

    return temp_project_dir


@pytest.fixture
def sample_subtask() -> Subtask:
    """Create a sample subtask."""
    return Subtask(
        id="test-subtask-1",
        description="Implement feature X",
        status=SubtaskStatus.PENDING,
    )
