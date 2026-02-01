# Task Initialization - Session 1

You are setting up the foundation for a long-running coding task using RASEN orchestrator.
This session creates everything future sessions need to work effectively.

## Your Task
{task_description}

## Working Directory
{project_dir}

---

## STEP 0: READ ALL REFERENCED DOCUMENTATION (MANDATORY)

**Before doing ANYTHING else**, you MUST:

1. **Identify all referenced docs** in the task description above
   - Look for: `docs/*.md`, `*.md`, `task.md`, `tasks.md`, `testing.md`, `coding-style.md`, etc.
   - Check project root AND `docs/` directory

2. **READ each referenced file completely**
   - Use the Read tool to load each file
   - Do NOT skip this step
   - Do NOT summarize from memory — actually read the files

3. **Extract existing task definitions** if present:
   - If task.md/tasks.md contains numbered tasks → USE THOSE EXACTLY
   - Copy task descriptions VERBATIM
   - Copy acceptance criteria VERBATIM
   - Copy test requirements VERBATIM
   - Copy dependencies as specified

4. **Extract testing requirements** from testing.md:
   - Understand the test layers (unit, integration, e2e, live)
   - Note which tasks require live tests (external services)
   - Include test file paths in subtask definitions

5. **Extract coding standards** from coding-style.md:
   - Note required tools (ruff, mypy, etc.)
   - Note formatting requirements
   - These apply to ALL subtasks

**DO NOT PROCEED until you have read all referenced documentation.**

---

## Required Outputs

### 1. Create `init.sh` - Development environment setup
   - Install dependencies
   - Set up environment variables
   - Any project-specific setup

### 2. Create `.rasen/state.json` - Implementation plan

**CRITICAL: If the referenced docs contain task definitions, USE THEM.**

For each subtask, include:
- `id`: Task ID (string, e.g., "1", "2", "1.1")
- `title`: Short title
- `description`: Full description (copy from source docs if available)
- `status`: "pending"
- `files`: Files to create/modify
- `tests`: Test files required (including live tests if external services)
- `dependencies`: IDs of prerequisite tasks
- `acceptance_criteria`: List of criteria (COPY VERBATIM from source docs)

**JSON Schema:**
{task_plan_schema}

### 3. Create `.rasen/progress.txt` - Session notes
   - Document which docs were read
   - Note any assumptions made
   - List key decisions

### 4. Make initial git commit

---

## Critical Rules

- It is UNACCEPTABLE to skip reading referenced documentation
- It is UNACCEPTABLE to invent tasks when they're already defined in docs
- It is UNACCEPTABLE to summarize or simplify existing acceptance criteria
- It is UNACCEPTABLE to skip test requirements from testing.md
- It is UNACCEPTABLE to create subtasks without acceptance_criteria
- Each subtask MUST include test files (unit, integration, live as appropriate)
- If a task involves external services (LLM, database, API), it MUST have live tests

## Checklist Before Completing

- [ ] Read ALL referenced .md files in task description
- [ ] Used existing task definitions if present (not invented new ones)
- [ ] Copied acceptance criteria VERBATIM from source docs
- [ ] Included test requirements from testing.md
- [ ] Added live test requirements for tasks with external services
- [ ] Created init.sh
- [ ] Created .rasen/state.json with proper schema
- [ ] Created .rasen/progress.txt with session notes
- [ ] Made git commit

## Output Format

When complete, output:
```xml
<event topic="init.done">Read {n} docs. Created {m} subtasks from {source}. Ready for coding sessions.</event>
```

Where `{source}` is either "existing task definitions" or "task breakdown".
