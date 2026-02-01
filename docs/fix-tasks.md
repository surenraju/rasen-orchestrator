# RASEN Orchestrator Bug Fixes

**Priority:** Critical
**Scope:** Fix core orchestration bugs

---

## Bug 1: get_next_subtask() ignores IN_PROGRESS tasks

**File:** `src/rasen/stores/plan_store.py`

**Current behavior (broken):**
```python
def get_next_subtask(self) -> Subtask | None:
    for subtask in plan.subtasks:
        if subtask.status == SubtaskStatus.PENDING:  # Only checks PENDING!
            return subtask
    return None
```

**Required fix:**
```python
def get_next_subtask(self) -> Subtask | None:
    # First, check for in_progress tasks (resume interrupted work)
    for subtask in plan.subtasks:
        if subtask.status == SubtaskStatus.IN_PROGRESS:
            return subtask
    # Then, check for pending tasks
    for subtask in plan.subtasks:
        if subtask.status == SubtaskStatus.PENDING:
            return subtask
    return None
```

**Acceptance Criteria:**
- [ ] IN_PROGRESS tasks are returned before PENDING
- [ ] Interrupted tasks resume correctly
- [ ] Unit test verifies IN_PROGRESS priority
- [ ] Unit test verifies PENDING fallback

---

## Bug 2: qa.per_subtask not implemented in loop.py

**File:** `src/rasen/loop.py`

**Current behavior (broken):**
- `config.qa.per_subtask` exists in config
- Review has per_subtask logic (line ~247)
- QA only runs after ALL tasks complete
- Setting `qa.per_subtask: true` does nothing

**Required fix:**
Add per-subtask QA logic similar to Review logic in `_run_session()` method:

```python
# After subtask completion validation (around line 250):
if review_result is None or review_result.passed:
    # NEW: Run per-subtask QA if enabled
    qa_result = None
    if self.config.qa.enabled and self.config.qa.per_subtask:
        logger.info(f"Running per-subtask QA for {subtask.id}")
        qa_result = run_qa_for_subtask(
            self.config, subtask, self.project_dir, commit_before
        )
    
    if qa_result is None or qa_result.passed:
        self.plan_store.mark_complete(subtask.id)
        # ... rest of completion logic
    else:
        logger.warning(f"Subtask {subtask.id} completed but failed QA")
        # Record QA rejection for recovery
        # ... rejection handling
```

**Acceptance Criteria:**
- [ ] QA runs after each subtask when `qa.per_subtask: true`
- [ ] QA rejection prevents marking subtask complete
- [ ] QA issues recorded in recovery store
- [ ] Existing end-of-build QA still works when `per_subtask: false`
- [ ] Unit test for per-subtask QA flow

---

## Bug 3: Need run_qa_for_subtask() function

**File:** `src/rasen/qa.py`

**Current behavior:**
- Only `run_qa_loop()` exists for full build QA
- No function for single subtask QA

**Required fix:**
Add `run_qa_for_subtask()` function:

```python
def run_qa_for_subtask(
    config: Config,
    subtask: Subtask,
    project_dir: Path,
    baseline_commit: str,
) -> QAResult:
    """Run QA validation for a single completed subtask.
    
    Args:
        config: RASEN configuration
        subtask: Subtask that was just completed
        project_dir: Project directory
        baseline_commit: Commit before subtask started
        
    Returns:
        QAResult with passed status and issues
    """
    # Similar to run_qa_loop but for single subtask
    # Check acceptance criteria
    # Verify tests exist and pass
    # Check for live tests if external services involved
```

**Acceptance Criteria:**
- [ ] Function validates single subtask acceptance criteria
- [ ] Returns QAResult with passed/issues
- [ ] Checks if tests exist for the subtask
- [ ] Unit test for subtask QA

---

## Testing Requirements

All fixes must include:
- [ ] Unit tests in `tests/unit/`
- [ ] Integration tests if needed
- [ ] All existing tests must pass
- [ ] `uv run ruff check src/` passes
- [ ] `uv run mypy src/` passes

---

## Definition of Done

- [ ] All 3 bugs fixed
- [ ] All tests pass: `uv run pytest`
- [ ] Linting passes: `uv run ruff check src/`
- [ ] Type checking passes: `uv run mypy src/`
- [ ] Changes committed with descriptive messages
