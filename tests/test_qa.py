"""Tests for QA validation loop functionality."""

from __future__ import annotations

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
)
from rasen.models import ImplementationPlan, QAState, Subtask, SubtaskStatus
from rasen.qa import QAHistory, QAResult, run_qa_loop


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create test project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    rasen_dir = project_dir / ".rasen"
    rasen_dir.mkdir()
    return project_dir


@pytest.fixture
def test_config_qa_enabled(test_project: Path) -> Config:
    """Create test configuration with QA enabled."""
    return Config(
        project=ProjectConfig(name="test-project", root=str(test_project.parent)),
        orchestrator=OrchestratorConfig(
            max_iterations=10,
            session_delay_seconds=0,
            session_timeout_seconds=60,
        ),
        agent=AgentConfig(model="claude-sonnet-4-20250514"),
        memory=MemoryConfig(enabled=False, path=str(test_project / ".rasen" / "memories.md")),
        backpressure=BackpressureConfig(require_tests=False, require_lint=False),
        stall_detection=StallDetectionConfig(),
        background=BackgroundConfig(
            status_file=str(test_project / ".rasen" / "status.json"),
            pid_file=str(test_project / ".rasen" / "rasen.pid"),
            log_file=str(test_project / ".rasen" / "rasen.log"),
        ),
        review=ReviewConfig(enabled=False),
        qa=QAConfig(enabled=True, max_iterations=5, recurring_issue_threshold=3),
    )


@pytest.fixture
def test_config_qa_disabled(test_project: Path) -> Config:
    """Create test configuration with QA disabled."""
    return Config(
        project=ProjectConfig(name="test-project", root=str(test_project.parent)),
        orchestrator=OrchestratorConfig(
            max_iterations=10,
            session_delay_seconds=0,
            session_timeout_seconds=60,
        ),
        agent=AgentConfig(model="claude-sonnet-4-20250514"),
        memory=MemoryConfig(enabled=False, path=str(test_project / ".rasen" / "memories.md")),
        backpressure=BackpressureConfig(require_tests=False, require_lint=False),
        stall_detection=StallDetectionConfig(),
        background=BackgroundConfig(
            status_file=str(test_project / ".rasen" / "status.json"),
            pid_file=str(test_project / ".rasen" / "rasen.pid"),
            log_file=str(test_project / ".rasen" / "rasen.log"),
        ),
        review=ReviewConfig(enabled=False),
        qa=QAConfig(enabled=False, max_iterations=5, recurring_issue_threshold=3),
    )


@pytest.fixture
def sample_plan() -> ImplementationPlan:
    """Create a sample implementation plan."""
    return ImplementationPlan(
        task_name="Build feature X",
        subtasks=[
            Subtask(id="1", description="Task 1", status=SubtaskStatus.COMPLETED),
            Subtask(id="2", description="Task 2", status=SubtaskStatus.COMPLETED),
        ],
    )


def test_qa_loop_disabled(
    test_config_qa_disabled: Config,
    test_project: Path,
    sample_plan: ImplementationPlan,
) -> None:
    """Test that QA loop returns True immediately when disabled."""
    with patch("rasen.qa.run_claude_session") as mock_session:
        result = run_qa_loop(
            config=test_config_qa_disabled,
            plan=sample_plan,
            project_dir=test_project,
            baseline_commit="abc123",
            task_description="Build feature X",
        )
        assert result.passed is True
        mock_session.assert_not_called()


def test_qa_loop_approved_on_first_try(
    test_config_qa_enabled: Config,
    test_project: Path,
    sample_plan: ImplementationPlan,
) -> None:
    """Test QA loop when plan indicates QA approved."""
    # Mock Claude session
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.session_id = "test-session-123"

    # Create a plan with QA approved
    approved_plan = ImplementationPlan(
        task_name="Build feature X",
        subtasks=sample_plan.subtasks,
        qa=QAState(status="approved", issues=[]),
    )

    # Mock PlanStore to return approved plan
    mock_plan_store = MagicMock()
    mock_plan_store.load.return_value = approved_plan

    with (
        patch("rasen.qa.run_claude_session", return_value=mock_result),
        patch("rasen.qa.get_git_diff", return_value="mock diff"),
        patch("rasen.qa.PlanStore", return_value=mock_plan_store),
    ):
        result = run_qa_loop(
            config=test_config_qa_enabled,
            plan=sample_plan,
            project_dir=test_project,
            baseline_commit="abc123",
            task_description="Build feature X",
        )
        assert result.passed is True


def test_qa_loop_rejected_then_approved(
    test_config_qa_enabled: Config,
    test_project: Path,
    sample_plan: ImplementationPlan,
) -> None:
    """Test QA loop when QA rejects first, then approves after fix."""
    call_count = [0]

    def mock_qa_session(*_args: object, **_kwargs: object) -> MagicMock:
        call_count[0] += 1
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        result.session_id = f"test-session-{call_count[0]}"
        return result

    # Track plan store calls
    plan_load_count = [0]

    def mock_plan_load() -> ImplementationPlan:
        plan_load_count[0] += 1
        if plan_load_count[0] == 1:
            # First QA session: rejected
            return ImplementationPlan(
                task_name="Build feature X",
                subtasks=sample_plan.subtasks,
                qa=QAState(
                    status="rejected",
                    issues=["Missing unit tests", "Test coverage below 60%"],
                ),
            )
        else:
            # After fix: approved
            return ImplementationPlan(
                task_name="Build feature X",
                subtasks=sample_plan.subtasks,
                qa=QAState(status="approved", issues=[]),
            )

    mock_plan_store = MagicMock()
    mock_plan_store.load.side_effect = mock_plan_load

    with (
        patch("rasen.qa.run_claude_session", side_effect=mock_qa_session),
        patch("rasen.qa.get_git_diff", return_value="mock diff"),
        patch("rasen.qa.PlanStore", return_value=mock_plan_store),
    ):
        result = run_qa_loop(
            config=test_config_qa_enabled,
            plan=sample_plan,
            project_dir=test_project,
            baseline_commit="abc123",
            task_description="Build feature X",
        )
        assert result.passed is True
        # 1 QA reject + 1 coder fix + 1 QA approve
        assert call_count[0] == 3


def test_qa_loop_recurring_issues_escalation(
    test_config_qa_enabled: Config,
    test_project: Path,
    sample_plan: ImplementationPlan,
) -> None:
    """Test QA loop creates escalation file when same issue occurs 3+ times."""
    call_count = [0]

    def mock_qa_session(*_args: object, **_kwargs: object) -> MagicMock:
        call_count[0] += 1
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        result.session_id = f"test-session-{call_count[0]}"
        return result

    # Always return rejected with same issue
    def mock_plan_load() -> ImplementationPlan:
        return ImplementationPlan(
            task_name="Build feature X",
            subtasks=sample_plan.subtasks,
            qa=QAState(status="rejected", issues=["Test coverage below 60%"]),
        )

    mock_plan_store = MagicMock()
    mock_plan_store.load.side_effect = mock_plan_load

    with (
        patch("rasen.qa.run_claude_session", side_effect=mock_qa_session),
        patch("rasen.qa.get_git_diff", return_value="mock diff"),
        patch("rasen.qa.PlanStore", return_value=mock_plan_store),
    ):
        result = run_qa_loop(
            config=test_config_qa_enabled,
            plan=sample_plan,
            project_dir=test_project,
            baseline_commit="abc123",
            task_description="Build feature X",
        )
        # Should fail due to recurring issues
        assert result.passed is False

        # Escalation file should be created
        escalation_file = test_project / "QA_ESCALATION.md"
        assert escalation_file.exists()
        content = escalation_file.read_text()
        assert "test coverage below 60%" in content.lower()
        assert "occurred" in content.lower()


def test_qa_loop_max_iterations_exceeded(
    test_config_qa_enabled: Config,
    test_project: Path,
    sample_plan: ImplementationPlan,
) -> None:
    """Test QA loop fails when max iterations exceeded without approval."""
    # Config has max_iterations=5, recurring_threshold=3
    # Use different issues each time to avoid recurring detection
    call_count = [0]

    def mock_qa_session(*_args: object, **_kwargs: object) -> MagicMock:
        call_count[0] += 1
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        result.session_id = f"test-session-{call_count[0]}"
        return result

    # Return different issue each time
    issue_count = [0]

    def mock_plan_load() -> ImplementationPlan:
        issue_count[0] += 1
        return ImplementationPlan(
            task_name="Build feature X",
            subtasks=sample_plan.subtasks,
            qa=QAState(status="rejected", issues=[f"Issue number {issue_count[0]}"]),
        )

    mock_plan_store = MagicMock()
    mock_plan_store.load.side_effect = mock_plan_load

    with (
        patch("rasen.qa.run_claude_session", side_effect=mock_qa_session),
        patch("rasen.qa.get_git_diff", return_value="mock diff"),
        patch("rasen.qa.PlanStore", return_value=mock_plan_store),
    ):
        result = run_qa_loop(
            config=test_config_qa_enabled,
            plan=sample_plan,
            project_dir=test_project,
            baseline_commit="abc123",
            task_description="Build feature X",
        )
        assert result.passed is False


def test_qa_history_tracks_issues() -> None:
    """Test QAHistory correctly tracks and detects recurring issues."""
    history = QAHistory()

    # Record same issue 3 times
    history.record(QAResult(approved=False, issues=["Test coverage low"]))
    assert not history.has_recurring_issues(3)

    history.record(QAResult(approved=False, issues=["Test coverage low"]))
    assert not history.has_recurring_issues(3)

    history.record(QAResult(approved=False, issues=["Test coverage low"]))
    assert history.has_recurring_issues(3)

    recurring = history.get_recurring_issues(3)
    assert len(recurring) == 1
    assert recurring[0][0] == "test coverage low"  # normalized
    assert recurring[0][1] == 3


def test_qa_result_model() -> None:
    """Test QAResult correctly stores approval and issues."""
    approved = QAResult(approved=True)
    assert approved.approved is True
    assert approved.issues == []

    rejected = QAResult(approved=False, issues=["Issue 1", "Issue 2"])
    assert rejected.approved is False
    assert len(rejected.issues) == 2
