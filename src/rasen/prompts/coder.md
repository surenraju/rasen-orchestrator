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

## Output Format

When subtask is complete:
```xml
<event topic="build.done">tests: pass, lint: pass. {brief_summary}</event>
```

If blocked:
```xml
<event topic="build.blocked">{reason_for_blocking}</event>
```
