# Task Initialization - Session 1

You are setting up the foundation for a long-running coding task using RASEN orchestrator.
This session creates everything future sessions need to work effectively.

## Your Task
write fibbanachi using python

## Working Directory
{project_dir}

## Required Outputs

1. **Create `init.sh`** - Script to set up development environment
   - Install dependencies
   - Set up environment variables
   - Any project-specific setup

2. **Create `.rasen/implementation_plan.json`** with ALL subtasks marked "pending"
   - Break task into 5-15 discrete subtasks
   - Each subtask completable in one session (< 30 minutes)
   - Order by dependency (foundations first)

3. **Create `claude-progress.txt`** - Initialize with session 1 notes
   - Document key decisions
   - Note any assumptions made

4. **Make initial git commit** documenting setup

## Critical Rules

- It is UNACCEPTABLE to skip creating the implementation plan
- It is UNACCEPTABLE to create subtasks without clear descriptions
- It is UNACCEPTABLE to skip the init.sh script
- Each subtask MUST be independently verifiable
- Use the provided JSON schema for implementation_plan.json

## Output Format

When complete, output:
```xml
<event topic="init.done">Created {n} subtasks. Ready for coding sessions.</event>
```
