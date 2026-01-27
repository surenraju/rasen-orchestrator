# Anthropic Long-Running Agents: Deep Dive Research

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Source:** https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents + linked pages

---

## Executive Summary

This document provides a comprehensive analysis of Anthropic's official approach to building long-running autonomous coding agents, extracted from their engineering blog and linked documentation. The key insight is the **Two-Agent Pattern** that enables Claude to work effectively across multiple context windows on complex projects spanning hours or days.

---

## 1. The Core Problem

Agents work in discrete sessions with **no memory between contexts**, forcing them to restart understanding of prior work repeatedly. Even frontier models like Opus 4.5 running in a loop across multiple context windows will fall short if given only a high-level prompt.

**Common Failure Modes:**
- Agent tries to "one-shot" the entire application
- Declares victory too early
- Leaves buggy/undocumented progress
- Marks features done without proper testing
- Wastes time figuring out app setup

---

## 2. The Two-Agent Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SESSION 1: INITIALIZER AGENT              │
│  Creates foundation for all future sessions                  │
│  - init.sh script                                           │
│  - claude-progress.txt                                       │
│  - feature_list.json (200+ features)                        │
│  - Initial git commit                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 SESSIONS 2+: CODING AGENT                    │
│  Makes incremental progress each session                     │
│  - Gets oriented (pwd, read progress, read logs)            │
│  - Selects highest-priority uncompleted feature             │
│  - Works on SINGLE feature only                             │
│  - Commits with descriptive message                         │
│  - Updates progress file                                     │
│  - Runs end-to-end tests                                    │
└─────────────────────────────────────────────────────────────┘
```

### Initializer Agent (Session 1 Only)

The first agent session performs critical setup:

1. **Creates `init.sh` script** - For running the development server
2. **Generates `claude-progress.txt`** - Logs all agent work
3. **Establishes initial git repository** - First commit documenting added files
4. **Writes `feature_list.json`** - 200+ features for complete scope
5. **Marks all features as "failing"** - Establishes complete work scope

### Coding Agent (Sessions 2+)

Each subsequent session follows this structured approach:

**Getting Oriented (Three Steps):**
1. Run `pwd` to confirm working directory
2. Read git logs and progress files for context
3. Select highest-priority uncompleted feature

**Development Process:**
1. Work on **single feature only**
2. Commit progress with descriptive git messages
3. Update progress file with session summary
4. Run end-to-end tests before finishing

---

## 3. Feature List JSON Structure

```json
{
  "category": "functional",
  "description": "New chat button creates fresh conversation",
  "steps": [
    "Navigate to main interface",
    "Click 'New Chat' button",
    "Verify new conversation created",
    "Check chat area shows welcome state",
    "Verify conversation in sidebar"
  ],
  "passes": false
}
```

**Critical Constraints:**
- Agents may **only modify the `passes` field**
- Strong instructions forbid removing or editing test descriptions
- "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality"

**Why JSON?** Models are "less likely to inappropriately change or overwrite JSON files compared to Markdown."

---

## 4. State Persistence Mechanisms

### Progress File (`claude-progress.txt`)

- Central hub for understanding project state
- Documents what agents accomplished
- Enables quick orientation in new context windows

**Example Format:**
```text
Session 3 progress:
- Fixed authentication token validation
- Updated user model to handle edge cases
- Next: investigate user_management test failures (test #2)
- Note: Do not remove tests as this could lead to missing functionality
```

### Git History

- Provides recovery mechanism for reverting failed changes
- Enables returning to last known stable state
- Offers clear documentation of development trajectory
- **Key insight:** Git provides both state tracking AND checkpoints that can be restored

### Feature List (`feature_list.json`)

- Prevents premature project completion
- Provides clear roadmap of remaining work
- Forces incremental feature-by-feature development

**Structured State Format:**
```json
{
  "tests": [
    {"id": 1, "name": "authentication_flow", "status": "passing"},
    {"id": 2, "name": "user_management", "status": "failing"},
    {"id": 3, "name": "api_endpoints", "status": "not_started"}
  ],
  "total": 200,
  "passing": 150,
  "failing": 25,
  "not_started": 25
}
```

---

## 5. Session Initialization Sequence

A typical coding agent session begins with:

```
[Assistant] Getting bearings, understanding current state
[Tool Use] pwd
[Tool Use] read claude-progress.txt
[Tool Use] read feature_list.json
[Assistant] Checking git logs
[Tool Use] bash - git log --oneline -20
[Tool Use] Starts development server
[Assistant] Verify fundamental features still working
[Tests basic functionality]
[Assistant] Core features working well; reviewing remaining work
[Starts work on new feature]
```

---

## 6. Testing Infrastructure

### The Problem

Claude struggled with proper feature verification until explicit testing guidance was provided:

- Model marked features complete without end-to-end verification
- Unit tests and `curl` commands insufficient to catch real issues
- Model couldn't recognize features failing in actual usage

### The Solution

- **Puppeteer MCP** for browser automation
- Agents test features **as human users would**
- Dramatic performance improvement once proper testing tools available

### Known Limitations

- Claude cannot see browser-native alert modals through Puppeteer
- Features relying on alert boxes showed higher bug rates

---

## 7. Failure Modes & Interventions

| Problem | Initializer Fix | Coding Agent Fix |
|---------|-----------------|------------------|
| Declares victory too early | Feature list file with 200+ features | Read feature list; work on one feature |
| Leaves buggy/undocumented progress | Initial git repo + progress notes | Read progress/logs; test; commit + update |
| Marks features done prematurely | Feature list established | Self-verify; only mark "passing" after testing |
| Wastes time figuring out app setup | Write `init.sh` script | Read `init.sh` at session start |

---

## 8. Multi-Context Window Best Practices

### From Claude 4 Prompting Guide

1. **Use different prompt for first context window**
   - First window: set up framework (write tests, create setup scripts)
   - Future windows: iterate on a todo-list

2. **Have model write tests in structured format**
   - Create tests before starting work
   - Keep track in structured format (e.g., `tests.json`)
   - Remind Claude: "It is unacceptable to remove or edit tests"

3. **Set up quality of life tools**
   - Create setup scripts (e.g., `init.sh`)
   - Gracefully start servers, run test suites, linters
   - Prevents repeated work when continuing from fresh context

4. **Starting fresh vs compacting**
   - Consider starting with brand new context window over compaction
   - Claude 4.5 models extremely effective at discovering state from filesystem
   - Be prescriptive about how to start:
     - "Call pwd; you can only read and write files in this directory"
     - "Review progress.txt, tests.json, and the git logs"
     - "Manually run through fundamental integration test before new features"

5. **Provide verification tools**
   - Tools like Playwright MCP server
   - Computer use capabilities for testing UIs
   - Verify correctness without continuous human feedback

6. **Encourage complete usage of context**
   - "This is a very long task, plan out work clearly"
   - "Spend entire output context working on the task"
   - "Don't run out of context with significant uncommitted work"

---

## 9. Context Awareness Prompting

### Sample Prompt for Long-Running Tasks

```text
Your context window will be automatically compacted as it approaches its limit,
allowing you to continue working indefinitely from where you left off. Therefore:

- Do not stop tasks early due to token budget concerns
- As you approach your token budget limit, save your current progress and state
  to memory before the context window refreshes
- Always be as persistent and autonomous as possible
- Complete tasks fully, even if the end of your budget is approaching
- Never artificially stop any task early regardless of the context remaining
```

---

## 10. Agent SDK Architecture

### Core Pattern

**Gather Context → Take Action → Verify Work → Repeat**

### Built-in Tools

| Tool | What it does |
|------|--------------|
| **Read** | Read any file in the working directory |
| **Write** | Create new files |
| **Edit** | Make precise edits to existing files |
| **Bash** | Run terminal commands, scripts, git operations |
| **Glob** | Find files by pattern (`**/*.ts`, `src/**/*.py`) |
| **Grep** | Search file contents with regex |
| **WebSearch** | Search the web for current information |
| **WebFetch** | Fetch and parse web page content |
| **AskUserQuestion** | Ask clarifying questions |

### Session Management

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    session_id = None

    # First query: capture the session ID
    async for message in query(
        prompt="Read the authentication module",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Glob"])
    ):
        if hasattr(message, 'subtype') and message.subtype == 'init':
            session_id = message.session_id

    # Resume with full context from the first query
    async for message in query(
        prompt="Now find all places that call it",
        options=ClaudeAgentOptions(resume=session_id)
    ):
        if hasattr(message, "result"):
            print(message.result)

asyncio.run(main())
```

### Subagent Definition

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async for message in query(
    prompt="Use the code-reviewer agent to review this codebase",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep", "Task"],
        agents={
            "code-reviewer": AgentDefinition(
                description="Expert code reviewer for quality and security reviews.",
                prompt="Analyze code quality and suggest improvements.",
                tools=["Read", "Glob", "Grep"]
            )
        }
    )
):
    if hasattr(message, "result"):
        print(message.result)
```

---

## 11. Autonomous Coding Demo Implementation

### Project Structure

```
autonomous-coding/
├── autonomous_agent_demo.py    # Main entry point
├── agent.py                     # Agent session logic
├── client.py                    # Claude SDK client configuration
├── security.py                  # Bash command allowlist & validation
├── progress.py                  # Progress tracking utilities
├── prompts.py                   # Prompt loading utilities
├── prompts/
│   ├── app_spec.txt            # Application specification
│   ├── initializer_prompt.md   # First session prompt
│   └── coding_prompt.md        # Continuation session prompt
└── requirements.txt             # Python dependencies
```

### Generated Project Structure

```
my_project/
├── feature_list.json           # Test cases (source of truth)
├── app_spec.txt                # Copied specification
├── init.sh                      # Environment setup script
├── claude-progress.txt         # Session progress notes
├── .claude_settings.json       # Security settings
└── [application files]         # Generated application code
```

### Security Model

**Defense-in-depth approach:**

1. **OS-level Sandbox**: Bash commands run in isolated environment
2. **Filesystem Restrictions**: File operations restricted to project directory only
3. **Bash Allowlist**: Only specific commands permitted:
   - File inspection: `ls`, `cat`, `head`, `tail`, `wc`, `grep`
   - Node.js: `npm`, `node`
   - Version control: `git`
   - Process management: `ps`, `lsof`, `sleep`, `pkill`

### Timing Expectations

- **First session (initialization)**: Several minutes - generates 200 test cases
- **Subsequent sessions**: 5-15 minutes per iteration
- **Full app (200 features)**: **Many hours** across multiple sessions

---

## 12. Claude Code Best Practices Integration

### CLAUDE.md Configuration

Store concise, human-readable documentation:
- Bash command reference
- Core utility functions
- Code style conventions
- Testing procedures
- Repository etiquette
- Environment setup instructions
- Project-specific quirks

### Extended Thinking Activation

Use specific phrases for increasing computation budgets:
- "think" (minimal budget)
- "think hard" (medium budget)
- "think harder" (higher budget)
- "ultrathink" (maximum budget)

### Effective Workflow Patterns

**Explore → Plan → Code → Commit:**
1. Ask Claude to read files/images/URLs without writing code
2. Request planning with explicit thinking mode
3. Optionally document plans in GitHub issues
4. Implement solutions with verification checks
5. Create PRs and update documentation

**Test-Driven Development:**
1. Write tests from expected input/output pairs
2. Run and confirm failures
3. Commit test files
4. Implement code to pass tests through iteration
5. Have subagents verify against overfitting
6. Commit completed implementation

### Multi-Claude Review Pattern

1. Claude A writes code
2. `/clear` or start Claude B
3. Claude B reviews first Claude's work
4. `/clear` again
5. Claude C edits based on feedback

---

## 13. Key Implementation Principles

### From Anthropic Engineering

1. **State persistence through JSON** - Less likely to be corrupted by LLMs than Markdown
2. **Git as communication** - Commits communicate intent between sessions
3. **Incremental development** - Single-feature-per-session approach critical
4. **Clean state philosophy** - Code must be "mergeable to main branch"
5. **Verification tools essential** - Puppeteer MCP for browser automation
6. **Strongly-worded instructions** - "It is unacceptable to remove or edit tests"

### Human Engineering Inspiration

The solution draws directly from how human software engineers work across shifts:
- Clear handoff documentation
- Clean commits
- Progress logs
- Systematic feature tracking

This prevents context loss between sessions.

---

## 14. Recommended Implementation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR LAYER                        │
│  - Manages session lifecycle                                │
│  - Tracks iteration count                                   │
│  - Handles 3-second delay between sessions                  │
│  - Auto-continues until Ctrl+C                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGENT SESSION                             │
│  - Fresh context window each iteration                      │
│  - Reads state from filesystem                              │
│  - Executes single feature                                  │
│  - Persists progress to files                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    STATE LAYER                               │
│  - feature_list.json (structured state)                     │
│  - claude-progress.txt (unstructured notes)                 │
│  - Git history (checkpoints + documentation)                │
│  - init.sh (environment setup)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    VERIFICATION LAYER                        │
│  - Puppeteer MCP for browser automation                     │
│  - End-to-end tests before marking "passing"                │
│  - Human-like feature verification                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 15. Future Research Directions

**Open Questions from Anthropic:**
- Single general-purpose agent vs. multi-agent architecture better?
- Could specialized agents (testing, QA, cleanup) improve sub-tasks?
- How to generalize beyond web app development (scientific research, financial modeling)?

---

## 16. Source References

### Primary Sources

| Document | URL |
|----------|-----|
| Effective Harnesses for Long-Running Agents | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| Claude Code Best Practices | https://www.anthropic.com/engineering/claude-code-best-practices |
| Building Agents with Claude Agent SDK | https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk |
| Autonomous Coding Demo | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding |

### Documentation

| Document | URL |
|----------|-----|
| Agent SDK Overview | https://platform.claude.com/docs/en/agent-sdk/overview |
| Claude 4 Prompting Best Practices | https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices |
| Claude Code Memory | https://code.claude.com/docs/en/memory |
| Claude Code Subagents | https://code.claude.com/docs/en/sub-agents |

### Authors & Credits

**Written by:** Justin Young (Anthropic)

**Contributors:** David Hershey, Prithvi Rajasakeran, Jeremy Hadfield, Naia Bouscal, Michael Tingley, Jesse Mu, Jake Eaton, Marius Buleandara, Maggie Vo, Pedram Navid, Nadine Yasser, Alex Notov

**Teams:** Code RL and Claude Code teams at Anthropic

---

## 17. Quick Start Checklist

To implement this pattern in your project:

- [ ] Create `init.sh` script for environment setup
- [ ] Create `feature_list.json` with all features marked "failing"
- [ ] Create `claude-progress.txt` for session notes
- [ ] Initialize git repository with first commit
- [ ] Configure Puppeteer MCP for browser testing
- [ ] Write initializer prompt for first session
- [ ] Write coding prompt for subsequent sessions
- [ ] Set up security allowlist for bash commands
- [ ] Implement session loop with auto-continuation
- [ ] Add strongly-worded instructions about not editing tests

---

## Conclusion

The key insight from Anthropic's approach is that **long-running autonomous coding requires explicit state management and incremental development**. The two-agent pattern (initializer + coding) with structured state files (JSON feature lists, progress notes, git history) enables Claude to work effectively across multiple context windows.

The most critical elements are:
1. **JSON for structured state** (less likely to be corrupted)
2. **Git for checkpoints and communication**
3. **Single-feature-per-session** approach
4. **End-to-end verification** before marking features complete
5. **Strongly-worded instructions** preventing test modification

This mirrors how human engineering teams handle shift handoffs and enables truly autonomous long-running development.
