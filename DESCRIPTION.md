# RASEN (螺旋) - Agent Orchestrator

**"The spiral that never stops turning"**

Production-ready orchestrator for long-running autonomous coding tasks using Claude Code CLI. Built for unattended execution with intelligent validation, recovery, and human escalation.

## One-Line Description

> Multi-agent orchestrator that autonomously plans, implements, reviews, and validates complex coding tasks with built-in recovery, quality gates, and human escalation patterns.

## GitHub Description (280 chars)

> 螺旋 RASEN: Production orchestrator for autonomous coding tasks. Multi-agent workflow (Initializer→Coder→Reviewer→QA) with intelligent recovery, stall detection, recurring issue escalation, and beautiful status monitoring. Built on Claude Code CLI.

## Twitter/Social (240 chars)

> Introducing RASEN 螺旋 - autonomous multi-agent coding orchestrator. Plans → Implements → Reviews → Validates. Handles hours-long tasks unattended. Beautiful status UI, smart recovery, human escalation. Built on Claude Code.

## Elevator Pitch (30 seconds)

RASEN orchestrates complex coding tasks that take hours to complete. It breaks tasks into subtasks, implements them autonomously with Claude, validates through code review and QA loops, and escalates to humans when it detects recurring issues. Run it in the background, check status anytime, and get production-quality code.

## Key Differentiators

- **Multi-agent workflow**: Specialized agents for planning, coding, review, and QA
- **Read-only validators**: Reviewers can't accidentally break code
- **Recurring issue detection**: Escalates when stuck (3+ same issues)
- **Beautiful monitoring**: Rich status UI with progress bars and activity logs
- **Unattended execution**: Background mode with auto-resume
- **Per-project customization**: Customize prompts and config per project
- **Session tracking**: Every log tagged for easy debugging

## Target Users

- **Solo developers** running multi-hour feature implementations
- **Teams** needing consistent code quality validation
- **AI researchers** experimenting with agent orchestration patterns
- **Claude Code users** wanting autonomous task execution

## Tech Stack

Python 3.12+ • Claude Code CLI • Pydantic • uv • pytest • ruff • mypy

---

*Name Origin: **RA**ju + **S**ur**EN** = RASEN (螺旋 = Spiral in Japanese)*
