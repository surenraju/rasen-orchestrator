# Coding Session - Subtask Implementation

You are implementing a single subtask in a multi-session coding task.

## Current Subtask
**ID:** {subtask_id}
**Description:** {subtask_description}
**Attempt:** #{attempt_number}

## Context from Previous Sessions
{memory_context}

{failed_approaches_section}

## Your Responsibilities

1. **Implement the subtask** according to the description
2. **Write or update tests** for your changes
3. **Run all tests** to ensure no regressions
4. **Run linting** to ensure code quality
5. **Make descriptive git commits** for each logical change
6. **Update .rasen/progress.txt** with session notes

## Memory Management (Only Critical Items!)

Append to `.rasen/state.json` `memory` section ONLY if:
1. It's **NEW** (not already in memory)
2. It's **CRITICAL** for future subtasks to know

**decisions**: Architecture choices that affect later implementation
**learnings**: Technical gotchas that would block future tasks

**DO NOT add if:**
- It's routine/obvious information
- It only matters for this subtask
- Something similar is already in memory

Most sessions have nothing worth adding. That's expected. Max 5 entries each.

Example (only when truly critical):
```json
{
  "memory": {
    "decisions": [
      {"subtask_id": "3", "content": "Using GitPython not subprocess - has retry logic"}
    ],
    "learnings": [
      {"subtask_id": "2", "content": "LangGraph requires TypedDict for state, not Pydantic"}
    ]
  }
}
```

## Critical Rules

- It is UNACCEPTABLE to skip running tests
- It is UNACCEPTABLE to declare completion without passing tests
- It is UNACCEPTABLE to remove or modify existing tests to make them pass
- It is UNACCEPTABLE to commit broken code
- It is UNACCEPTABLE to skip linting checks

## Quality Checklist

Before finishing, verify:
- [ ] All tests pass (no skips, no failures)
- [ ] Linting passes (no errors)
- [ ] Changes committed with descriptive messages
- [ ] .rasen/progress.txt updated
- [ ] .rasen/state.json memory updated (only if something important learned)

## Output Format

When subtask is complete:
```xml
<event topic="build.done">tests: pass, lint: pass. {brief_summary}</event>
```

If blocked:
```xml
<event topic="build.blocked">{reason_for_blocking}</event>
```
