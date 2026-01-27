"""Tests for implementation plan store."""

from __future__ import annotations

from rasen.models import ImplementationPlan, Subtask, SubtaskStatus
from rasen.stores.plan_store import PlanStore


def test_plan_store_save_and_load(rasen_dir, sample_plan):
    """Test saving and loading a plan."""
    store = PlanStore(rasen_dir)

    store.save(sample_plan)
    loaded = store.load()

    assert loaded is not None
    assert loaded.task_name == sample_plan.task_name
    assert len(loaded.subtasks) == len(sample_plan.subtasks)


def test_plan_store_load_missing_plan(rasen_dir):
    """Test loading when no plan exists."""
    store = PlanStore(rasen_dir)

    loaded = store.load()

    assert loaded is None


def test_get_next_subtask_pending(rasen_dir):
    """Test getting next pending subtask."""
    store = PlanStore(rasen_dir)
    plan = ImplementationPlan(
        task_name="Test",
        subtasks=[
            Subtask(id="t1", description="Task 1", status=SubtaskStatus.COMPLETED),
            Subtask(id="t2", description="Task 2", status=SubtaskStatus.PENDING),
            Subtask(id="t3", description="Task 3", status=SubtaskStatus.PENDING),
        ],
    )
    store.save(plan)

    next_task = store.get_next_subtask()

    assert next_task is not None
    assert next_task.id == "t2"
    assert next_task.status == SubtaskStatus.PENDING


def test_get_next_subtask_none_pending(rasen_dir):
    """Test getting next subtask when all are complete."""
    store = PlanStore(rasen_dir)
    plan = ImplementationPlan(
        task_name="Test",
        subtasks=[
            Subtask(id="t1", description="Task 1", status=SubtaskStatus.COMPLETED),
            Subtask(id="t2", description="Task 2", status=SubtaskStatus.COMPLETED),
        ],
    )
    store.save(plan)

    next_task = store.get_next_subtask()

    assert next_task is None


def test_mark_in_progress(rasen_dir, sample_plan):
    """Test marking a subtask as in progress."""
    store = PlanStore(rasen_dir)
    store.save(sample_plan)

    store.mark_in_progress("task-1")

    plan = store.load()
    assert plan is not None
    subtask = next(s for s in plan.subtasks if s.id == "task-1")
    assert subtask.status == SubtaskStatus.IN_PROGRESS


def test_mark_complete(rasen_dir, sample_plan):
    """Test marking a subtask as complete."""
    store = PlanStore(rasen_dir)
    store.save(sample_plan)

    store.mark_complete("task-1")

    plan = store.load()
    assert plan is not None
    subtask = next(s for s in plan.subtasks if s.id == "task-1")
    assert subtask.status == SubtaskStatus.COMPLETED


def test_mark_failed(rasen_dir, sample_plan):
    """Test marking a subtask as failed."""
    store = PlanStore(rasen_dir)
    store.save(sample_plan)

    store.mark_failed("task-1")

    plan = store.load()
    assert plan is not None
    subtask = next(s for s in plan.subtasks if s.id == "task-1")
    assert subtask.status == SubtaskStatus.FAILED


def test_get_completion_stats(rasen_dir):
    """Test getting completion statistics."""
    store = PlanStore(rasen_dir)
    plan = ImplementationPlan(
        task_name="Test",
        subtasks=[
            Subtask(id="t1", description="T1", status=SubtaskStatus.COMPLETED),
            Subtask(id="t2", description="T2", status=SubtaskStatus.COMPLETED),
            Subtask(id="t3", description="T3", status=SubtaskStatus.PENDING),
            Subtask(id="t4", description="T4", status=SubtaskStatus.IN_PROGRESS),
        ],
    )
    store.save(plan)

    completed, total = store.get_completion_stats()

    assert completed == 2
    assert total == 4


def test_get_completion_stats_no_plan(rasen_dir):
    """Test completion stats with no plan."""
    store = PlanStore(rasen_dir)

    completed, total = store.get_completion_stats()

    assert completed == 0
    assert total == 0


def test_multiple_updates_preserve_data(rasen_dir):
    """Test multiple updates don't corrupt data."""
    store = PlanStore(rasen_dir)
    plan = ImplementationPlan(
        task_name="Test",
        subtasks=[
            Subtask(id="t1", description="Task 1"),
            Subtask(id="t2", description="Task 2"),
        ],
    )
    store.save(plan)

    # Multiple updates
    store.mark_in_progress("t1")
    store.mark_complete("t1")
    store.mark_in_progress("t2")

    # Verify state
    loaded = store.load()
    assert loaded is not None
    t1 = next(s for s in loaded.subtasks if s.id == "t1")
    t2 = next(s for s in loaded.subtasks if s.id == "t2")
    assert t1.status == SubtaskStatus.COMPLETED
    assert t2.status == SubtaskStatus.IN_PROGRESS
