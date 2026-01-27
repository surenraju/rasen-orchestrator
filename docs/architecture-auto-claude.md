# Auto-Claude Framework - Architecture Analysis

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Source:** /Auto-Claude

---

## 1. Overview

**Auto-Claude** is an autonomous multi-agent coding framework that plans, builds, and validates software autonomously using the Claude Agent SDK. It enables developers to describe features in natural language, and agents handle the complete workflow: specification creation, implementation planning, coding, quality assurance, and integration.

**Problem it Solves:**
- Automates the entire development workflow from spec to production-ready code
- Enables parallel coding with multiple agents working on different subtasks
- Provides self-validating QA with AI-driven issue resolution
- Ensures safe integration through isolated git worktrees
- Maintains cross-session context through Graphiti semantic memory

**Key Statistics:**
- Version: 2.7.5
- License: AGPL-3.0 (commercial licensing available)
- Platforms: Windows, macOS, Linux
- Backend: Python
- Frontend: Electron + React

---

## 2. Architecture Pattern

**Pattern Type:** Multi-Agent Hierarchical Orchestration with Semantic Memory

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AUTO-CLAUDE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Electron   │ →  │  Python     │ →  │  Claude     │                  │
│  │  Frontend   │    │  Backend    │    │  Agent SDK  │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         ↓                  ↓                  ↓                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Kanban UI  │    │  Spec       │    │  Planner    │                  │
│  │  Terminals  │    │  Pipeline   │    │  Agent      │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         ↓                  ↓                  ↓                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  i18n       │    │  Memory     │    │  Coder      │                  │
│  │  (React)    │    │  (Graphiti) │    │  Agent      │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                            ↓                  ↓                          │
│                     ┌─────────────┐    ┌─────────────┐                  │
│                     │  Security   │    │  QA Agents  │                  │
│                     │  (3-Layer)  │    │  (Review+Fix)│                 │
│                     └─────────────┘    └─────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **Separation of Concerns** - Python handles bookkeeping (memory, commits, progress); agents focus on coding
2. **Isolation via Worktrees** - Each spec gets isolated `git worktree`; parallel development without main branch risk
3. **Dual-Layer Memory** - Graphiti for semantic search, file-based as fallback
4. **Dynamic Security** - Project stack detection enables appropriate tooling

---

## 3. Core Components

### Project Structure

```
Auto-Claude/
├── apps/
│   ├── backend/           # Python orchestration
│   │   ├── cli/           # CLI commands
│   │   ├── agents/        # Agent implementations
│   │   ├── spec/          # Specification pipeline
│   │   ├── core/          # Client, worktree, workspace
│   │   ├── memory/        # File-based memory
│   │   ├── security/      # Security validators
│   │   ├── project/       # Project analyzer
│   │   ├── qa/            # QA reviewer and fixer
│   │   └── integrations/  # Graphiti, Linear, GitHub
│   └── frontend/          # Electron + React UI
│       ├── src/main/      # Electron main process
│       ├── src/renderer/  # React UI
│       └── src/shared/    # i18n, utilities
├── prompts/               # Agent instruction prompts
└── .auto-claude/          # Runtime artifacts
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `core/client.py` | Claude Agent SDK client factory |
| `agents/coder.py` | Coder agent implementation |
| `agents/planner.py` | Planner agent implementation |
| `agents/session.py` | Session management |
| `spec/pipeline/` | Spec creation orchestration |
| `memory/main.py` | File-based memory fallback |
| `integrations/graphiti/` | Semantic memory integration |
| `security/hooks.py` | Pre-tool-use validation |
| `qa/reviewer.py` | QA validation agent |
| `qa/fixer.py` | QA issue resolution agent |

---

## 4. Agent Implementation

### Does Auto-Claude Use SDK or CLI?

**Auto-Claude uses the Claude Agent SDK (CONFIRMED):**

```python
# /apps/backend/core/client.py
from core.client import create_client

client = create_client(
    project_dir=Path(...),
    spec_dir=Path(...),
    model="claude-sonnet-4-5-20250929",
    agent_type="coder",  # Determines tool permissions
    max_thinking_tokens=4096
)

response = client.create_agent_session(
    name="session-name",
    starting_message="Task description"
)
```

### Why SDK Over CLI

- Pre-configured security (sandbox, allowlists, hooks)
- Automatic MCP server integration
- Tool permissions based on agent role
- Session management and recovery

### Four Core Agent Types

| Agent | Purpose | Prompt File |
|-------|---------|-------------|
| **Planner** | Creates subtask-based implementation plans | `prompts/planner.md` |
| **Coder** | Implements individual subtasks | `prompts/coder.md` |
| **QA Reviewer** | Validates acceptance criteria | `prompts/qa_reviewer.md` |
| **QA Fixer** | Fixes issues identified by QA | `prompts/qa_fixer.md` |

### Tool Permissions by Agent Type

- **Planner:** Read-only filesystem, project analysis, git read
- **Coder:** Full filesystem write, git write, package managers, tests, subagent spawn
- **QA Reviewer:** Test execution, project inspection, Electron MCP
- **QA Fixer:** Filesystem write, git ops, test execution, Electron MCP

---

## 5. Session Management

### Session Lifecycle

```
1. INITIALIZE
   ├─ Load spec and implementation plan
   ├─ Load Graphiti context
   ├─ Get previous session memory
   └─ Compute next subtask

2. RUN AGENT
   ├─ Create SDK client
   ├─ Start agent session
   ├─ Agent works on subtask
   └─ Capture logs

3. POST-SESSION (Python - 100% reliable)
   ├─ Check for new commits
   ├─ Update implementation plan
   ├─ Record attempt result
   ├─ Update memory
   ├─ Sync back to main (if worktree mode)
   └─ Update Linear (if enabled)

4. RECOVERY
   ├─ If failed: RecoveryManager records attempt
   ├─ Next iteration: Try alternative approach
   └─ Max retries: Move to recovery prompt
```

### Memory System (Dual-Layer)

**Primary - Graphiti:**
- Semantic knowledge graph with LadybugDB (no Docker)
- Multi-LLM support: OpenAI, Anthropic, Azure, Ollama, Google
- Cross-session learning and context retrieval

**Fallback - File-based:**
- Location: `.auto-claude/specs/{spec}/memory/`
- Zero dependencies
- Session insights stored as JSON

---

## 6. State Persistence

### Storage Locations

| Path | Format | Purpose |
|------|--------|---------|
| `.auto-claude/specs/XXX-name/spec.md` | Markdown | Feature specification |
| `.auto-claude/specs/XXX-name/requirements.json` | JSON | Structured requirements |
| `.auto-claude/specs/XXX-name/context.json` | JSON | Discovered codebase context |
| `.auto-claude/specs/XXX-name/implementation_plan.json` | JSON | Subtask-based plan |
| `.auto-claude/specs/XXX-name/qa_report.md` | Markdown | QA results |
| `.auto-claude/specs/XXX-name/task_metadata.json` | JSON | Model & thinking config |
| `.auto-claude/specs/XXX-name/build-progress.txt` | Text | Status updates |
| `.auto-claude/status.json` | JSON | Real-time status |
| `.worktrees/{spec}/` | Directory | Isolated git worktree |

### Implementation Plan Format

```json
{
  "phases": [
    {
      "phase_id": "auth",
      "title": "Authentication Setup",
      "subtasks": [
        {
          "id": "auth-001",
          "description": "Create auth service",
          "status": "completed",
          "approach_used": "Used existing auth library",
          "good_commits": ["abc123"],
          "attempts": 1
        }
      ]
    }
  ]
}
```

---

## 7. Workflow Phases

### Spec Creation Pipeline (3-8 Phases by Complexity)

**SIMPLE (3 phases):**
```
Discovery → Quick Spec → Validation
```

**STANDARD (6-7 phases):**
```
Discovery → Historical Context → Requirements → [Research] → Context → Spec Writing → Planning → Validation
```

**COMPLEX (8 phases):**
```
Discovery → Historical Context → Requirements → Research → Context → Spec Writing → Self-Critique (ultrathink) → Planning → Validation
```

### Implementation Pipeline

```
SESSION 1: PLANNING
  └─ Planner creates implementation plan

SESSION N: CODING (N iterations)
  ├─ Find next pending subtask
  ├─ Coder implements
  ├─ Post-session processing (Python)
  └─ Repeat until complete

SESSION N+1: QA REVIEW
  ├─ QA Reviewer validates criteria
  ├─ E2E testing (Electron MCP)
  └─ Decision: PASS or CREATE_FIX_REQUEST

IF FAIL:
SESSION N+2: QA FIX
  ├─ Load QA_FIX_REQUEST.md
  ├─ QA Fixer resolves all issues
  └─ Loop back to QA REVIEW

IF PASS:
  └─ Ready for merge!
```

### Phase Configuration

| Phase | Default Model | Thinking Budget |
|-------|---------------|-----------------|
| Spec Creation | claude-sonnet | ultrathink (63999 tokens) |
| Planning | claude-sonnet | high (16384 tokens) |
| Coding | claude-sonnet | medium (4096 tokens) |
| QA | claude-sonnet | high (16384 tokens) |

---

## 8. Subagent Spawning

### Spawning via Task Tool

Coder agents can spawn subagents for parallel work:

```
Coder Agent sees: 3 independent subtasks
  ↓
Decision: Spawn subagents
  ↓
Uses Task tool to create 3 child tasks
  ↓
Each runs independently in parallel
  ↓
Main agent waits for all to complete
  ↓
Merge results
```

### Synchronization

- **Shared Memory:** Implementation plan across all agents
- **Atomic Updates:** Lock-protected file writes
- **No Race Conditions:** File-level locking
- **Recovery:** Failed subagent retried independently

### Git Worktree Strategy

```
main (user's branch)
  └── auto-claude/{spec-name}  ← spec branch
      └── .worktrees/{spec-name}/  ← working directory
```

**Workflow:**
1. Create worktree on spec branch from main
2. Build runs in isolated environment
3. User tests in `.worktrees/{spec-name}/`
4. User runs `--merge` to integrate
5. User pushes to remote when ready

---

## 9. Configuration

### Environment Variables

**Required:**
```bash
CLAUDE_CODE_OAUTH_TOKEN=<token>     # From: claude login
ANTHROPIC_API_KEY=<key>             # For Graphiti
```

**Optional - Graphiti:**
```bash
GRAPHITI_ENABLED=true|false
GRAPHITI_LLM_PROVIDER=anthropic|openai|azure|ollama|google
GRAPHITI_EMBEDDER_PROVIDER=openai|voyage|azure|ollama|google
GRAPHITI_HOST=localhost
GRAPHITI_PORT=9081
```

**Optional - Integrations:**
```bash
LINEAR_API_KEY=<key>
GITHUB_TOKEN=<token>
ELECTRON_MCP_ENABLED=true
ELECTRON_DEBUG_PORT=9222
```

**Optional - Development:**
```bash
DEBUG=true
EXTENDED_THINKING_BUDGET=4096|16384|63999
CLAUDE_MODEL=<model-id>
```

### CLI Examples

```bash
# Create spec
python spec_runner.py --interactive
python spec_runner.py --task "Add auth" --complexity simple

# Run build
python run.py --spec 001
python run.py --spec 001 --followup "Also add logout"

# Workspace management
python run.py --spec 001 --review
python run.py --spec 001 --merge
python run.py --spec 001 --discard

# QA operations
python run.py --spec 001 --qa
python run.py --spec 001 --qa-status

# List specs
python run.py --list
```

### task_metadata.json Configuration

```json
{
  "phaseModels": {
    "spec": "opus",
    "planning": "opus",
    "coding": "sonnet",
    "qa": "opus"
  },
  "phaseThinking": {
    "spec": "ultrathink",
    "planning": "high",
    "coding": "medium",
    "qa": "high"
  }
}
```

---

## 10. Key Files

### Entry Points

| File | Purpose |
|------|---------|
| `/apps/backend/run.py` | CLI entry point |
| `/apps/backend/cli/main.py` | Command routing |
| `/apps/backend/spec_runner.py` | Spec creation entry |
| `/apps/frontend/src/main/index.ts` | Electron main |

### Core Orchestration

| File | Purpose |
|------|---------|
| `core/client.py` | **SDK client factory (CRITICAL)** |
| `agents/coder.py` | Coder agent implementation |
| `agents/planner.py` | Planner agent implementation |
| `agents/session.py` | Session management |
| `agents/memory_manager.py` | Memory orchestration |

### Prompts (Agent Instructions)

| Prompt | Purpose |
|--------|---------|
| `prompts/spec_writer.md` | Spec creation (ultrathink) |
| `prompts/spec_critic.md` | Self-critique (ultrathink) |
| `prompts/planner.md` | Implementation planning |
| `prompts/coder.md` | Subtask implementation |
| `prompts/coder_recovery.md` | Recovery from stuck states |
| `prompts/qa_reviewer.md` | QA validation |
| `prompts/qa_fixer.md` | QA issue resolution |

### Security & Analysis

| File | Purpose |
|------|---------|
| `security/__init__.py` | Security module facade |
| `security/hooks.py` | Pre-tool-use validation |
| `security/validator.py` | Command validators |
| `project/analyzer.py` | Project stack detection |

---

## 11. Security Model

### Three-Layer Defense

**Layer 1: OS Sandbox**
- Bash commands run in isolation
- Cannot affect system outside project

**Layer 2: Filesystem Restrictions**
- Operations limited to project directory
- `.auto-claude/` metadata stays isolated
- No home directory access

**Layer 3: Dynamic Command Allowlist**
- Built from detected technology stack
- Base commands: Core shell utilities
- Stack commands: npm, python, docker, git, etc.
- Custom commands: User-defined in profile

### Project Stack Detection

1. Read `package.json` for Node projects
2. Read `pyproject.toml` / `setup.py` for Python
3. Scan for Docker, git, Makefile, etc.
4. Build comprehensive `TechnologyStack` object
5. Generate `.auto-claude-security.json` profile

---

## Summary

**Auto-Claude** is a sophisticated **multi-agent orchestration framework** that:

| Aspect | Implementation |
|--------|----------------|
| **Agent Execution** | Claude Agent SDK (`create_client()`) |
| **Architecture** | Multi-agent hierarchical with subagent spawning |
| **Session Management** | Per-subtask sessions with recovery |
| **State Persistence** | JSON plans + Markdown specs + Graphiti memory |
| **Parallel Execution** | Git worktrees + subagent spawning |
| **Quality Gates** | 4-phase QA loop (Review → Fix → Review → Pass) |
| **Language** | Python backend + Electron/React frontend |

**Key Differentiator:** Uses the **Claude Agent SDK** (not CLI), enabling sophisticated multi-agent coordination with semantic memory (Graphiti), automatic checkpointing, and cross-session learning.

**Production Status:** v2.7.5, AGPL-3.0 licensed, cross-platform support.
