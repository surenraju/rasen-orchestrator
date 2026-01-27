# RASEN Test Suite

## Test Coverage Summary

Current Status: **107 tests, 32% coverage** (Target: 80%+)

## Test Files

### Unit Tests

1. **test_exceptions.py** (10 tests) ✅
   - Exception hierarchy
   - StallDetectedError with termination reasons
   - Error inheritance

2. **test_models.py** (19 tests) ✅
   - Pydantic model validation
   - Enums (TerminationReason, SessionStatus, SubtaskStatus)
   - ImplementationPlan, Subtask, SessionResult, LoopState

3. **test_events.py** (17 tests) ✅
   - XML event parsing
   - Multiple events, malformed XML
   - Review/QA events

4. **test_validation.py** (19 tests) ✅
   - Backpressure validation
   - "tests: pass, lint: pass" evidence checking
   - Case insensitive matching

5. **test_config.py** (4 tests) ✅
   - YAML configuration loading
   - Default values
   - Review/QA enablement

6. **test_git.py** (14 tests) ✅
   - Git repository detection
   - Commit counting
   - Diff generation
   - Uncommitted changes detection

### Store Tests

7. **tests/stores/test_atomic.py** (14 tests) ✅
   - Atomic file write operations
   - File locking (fcntl/msvcrt)
   - Temp file cleanup
   - Unicode handling

8. **tests/stores/test_plan_store.py** (10 tests) ✅
   - Plan persistence
   - Subtask status tracking
   - Completion statistics
   - Multi-update integrity

### Remaining Tests Needed

- **test_prompts.py** - Prompt template rendering
- **tests/stores/test_recovery_store.py** - Attempt history, thrashing detection
- **tests/stores/test_memory_store.py** - Cross-session memory
- **tests/stores/test_status_store.py** - Status tracking
- **test_review.py** - Review loop integration
- **test_qa.py** - QA loop with recurring issue detection
- **test_loop.py** - Main orchestration loop
- **test_claude_runner.py** - Subprocess execution

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=rasen --cov-report=term-missing

# Specific file
uv run pytest tests/test_git.py -v

# Run in parallel
uv run pytest tests/ -n auto
```

## Test Fixtures (conftest.py)

- `temp_project_dir` - Temporary project directory
- `rasen_dir` - .rasen state directory
- `prompts_dir` - Prompt templates directory
- `test_config` - Test configuration with all settings
- `sample_plan` - 3-subtask implementation plan
- `git_repo` - Initialized git repository
- `sample_subtask` - Single subtask model
