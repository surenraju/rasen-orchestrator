# Claude Code Tools & Long-Running Tasks Research

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Purpose:** Deep research on Claude Code for long-running tasks, wrapper tools, and best approaches

---

## Executive Summary

This research covers how developers use Claude Code for long-running tasks, wrapper tools like AutoClaude, and the best approaches for autonomous coding sessions.

---

## 1. Claude Code Long-Running Task Configuration

### The Two-Agent Pattern (Official Anthropic)

**Source:** [Anthropic Engineering Blog](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

| Component | Purpose |
|-----------|---------|
| **Initializer Agent** | Sets up environment, creates `init.sh`, `claude-progress.txt`, JSON feature list |
| **Coding Agent** | Makes incremental progress, reads progress files, selects highest-priority feature |
| **State Persistence** | Git commits + JSON feature lists (200+ granular features marked pass/fail) |

**Key Configuration Options:**

| Feature | Configuration | Purpose |
|---------|--------------|---------|
| **Auto-Accept Mode** | Shift+Tab toggle | Autonomous work without confirming each edit |
| **Extended Thinking** | `MAX_THINKING_TOKENS` env var | Deeper reasoning for complex tasks |
| **Sandboxing** | `/sandbox` command | Reduces permission prompts by 84% |
| **Subagents** | `.claude/agents/` directory | Delegate specialized tasks in parallel |
| **Hooks** | Event-based triggers | Auto-run tests, linting at specific points |

### Parallel Session Management (Boris Cherny - Creator)

- Runs **5 local sessions + 5-10 remote sessions** simultaneously
- Each local session uses its own git checkout (not branches or worktrees)
- Remote sessions started with `&` from CLI
- Uses `--teleport` to move sessions back and forth

---

## 2. Major Claude Code Wrapper Tools

### Tool Comparison Table

| Tool | GitHub Stars | Category | Key Feature |
|------|-------------|----------|-------------|
| **Cline** | 57,000+ | VS Code Extension | 4M+ installs, human-in-the-loop |
| **Aider** | 36,000+ | Terminal AI Pair Programming | 15B tokens/week, repo mapping |
| **Continue.dev** | 26,000+ | IDE Extension | Free, headless mode |
| **Claude-Flow** | 12,800+ | Multi-Agent Orchestration | 64 agents, 175+ MCP tools |

### Aider
- **GitHub:** [Aider-AI/aider](https://github.com/Aider-AI/aider)
- **Command:** `aider --model sonnet --api-key anthropic=<key>`
- **Key Feature:** Repository mapping for intelligent multi-file edits
- **Integration:** [ai-claude-code-aider-integration](https://github.com/jfontestad/ai-claude-code-aider-integration)

### Cline (formerly Claude-Dev)
- **GitHub:** [cline/cline](https://github.com/cline/cline)
- **VS Code:** [saoudrizwan.claude-dev](https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev)
- **Features:** Autonomous coding, MCP support, Computer Use for browser automation
- **Cost:** $0.50-$2+ per session (high token usage)

### Claude-Flow
- **GitHub:** [ruvnet/claude-flow](https://github.com/ruvnet/claude-flow)
- **Status:** "Ranked #1 in agent-based frameworks"
- **Features:** 64 specialized agents, distributed swarm intelligence, RAG integration
- **Session Persistence:** [Wiki documentation](https://github.com/ruvnet/claude-flow/wiki/session-persistence)

### Oh-My-ClaudeCode
- **GitHub:** [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)
- **Modes:** Autopilot, Ultrapilot (3-5x parallel), Swarm, Pipeline, Ecomode
- **Cost Savings:** 30-50% via smart model routing

---

## 3. Session Persistence & Memory

### CLAUDE.md Memory Hierarchy

| Level | Location | Scope |
|-------|----------|-------|
| Global | `~/.claude/CLAUDE.md` | All projects |
| Project | `/project-root/CLAUDE.md` | Single project |
| Directory | `/project-root/frontend/CLAUDE.md` | Specific directory |
| Personal | `/project-root/CLAUDE.local.md` | Private (gitignored) |

### Session Resume Commands

| Command | Purpose |
|---------|---------|
| `claude -c` / `claude --continue` | Continue most recent conversation |
| `claude -r "abc123"` | Resume specific session by ID |
| `claude --resume` | View list of recent conversations |

### Context Management

| Command | Purpose |
|---------|---------|
| `/compact` | Strategically reduces context size |
| `/clear` | Fresh session start |
| `/context` | Debug context issues |
| `/memory` | Open memory files in editor |

---

## 4. Headless Mode & CI/CD

### Basic Headless Usage

```bash
# Basic headless query
claude -p "How many TypeScript files are in this project?"

# With JSON output for parsing
claude -p "Review this code" --output-format json

# With streaming JSON
claude -p "Analyze the codebase" --output-format stream-json
```

### Essential CLI Flags

| Flag | Description |
|------|-------------|
| `-p "query"` | Headless/print mode |
| `--output-format` | text/json/stream-json |
| `--allowedTools` | Restrict available tools |
| `--max-turns` | Limit agentic turns |
| `--model` | Select model (sonnet/opus) |

### GitHub Actions Integration

```yaml
name: Claude Assistant
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  claude-response:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

---

## 5. Multi-Agent Orchestration

### Built-in Subagents

| Subagent | Purpose |
|----------|---------|
| **Explore** | Fast, read-only codebase search |
| **Plan** | Research for plan mode context |
| **General-purpose** | Complex multi-step tasks |

### Custom Subagent Definition

```yaml
# .claude/agents/security-reviewer.md
---
name: security-reviewer
description: Reviews code for security vulnerabilities
tools:
  - Read
  - Grep
  - Glob
---
# Security Reviewer Agent
Analyze code for OWASP Top 10 vulnerabilities...
```

### Parallel Execution Patterns

**Git Worktrees + tmux:**
```bash
# Create isolated worktrees
git worktree add -b feature-auth ../auth-worktree
git worktree add -b feature-api ../api-worktree

# Run Claude in separate tmux sessions
tmux new-session -d -s agent1 'cd ../auth-worktree && claude'
tmux new-session -d -s agent2 'cd ../api-worktree && claude'
```

### Swarm Organization Patterns

1. **The Hive** - Single massive task queue for large-scale refactors
2. **Hierarchical** - Queen agent coordinates worker agents
3. **Mesh** - Peer-to-peer coordination
4. **Pipeline** - Sequential stage processing
5. **Adaptive** - Dynamic routing based on task characteristics

---

## 6. Claude Code vs Cursor Comparison

| Feature | Claude Code | Cursor |
|---------|-------------|--------|
| **Interface** | Terminal/CLI-first | IDE-based |
| **Parallel Agents** | Native subagent support | Up to 8 agents |
| **Context Window** | Full 200K tokens | Effective 70K-120K |
| **Best For** | Long-running autonomous tasks | Quick fixes, autocomplete |
| **Cost** | ~$10/hour (usage-based) | $20/month flat |

**Verdict:** Claude Code wins for long-running tasks; Cursor better for daily development.

---

## 7. Long-Running Session Solutions

### Community Tools

| Tool | GitHub | Approach |
|------|--------|----------|
| **Continuous Claude** | [AnandChowdhary/continuous-claude](https://github.com/AnandChowdhary/continuous-claude) | Loop with auto-PR creation |
| **Continuous Claude v3** | [parcadei/Continuous-Claude-v3](https://github.com/parcadei/Continuous-Claude-v3) | Hooks maintain state via ledgers |
| **Claude Cognitive** | [GMaN1911/claude-cognitive](https://github.com/GMaN1911/claude-cognitive) | Working memory, multi-instance coordination |
| **Claude Squad** | [smtg-ai/claude-squad](https://github.com/smtg-ai/claude-squad) | Multiple agents in separate workspaces |

### The "Document & Clear" Pattern

1. Have Claude dump plan and progress into a `.md` file
2. Run `/clear` to reset state
3. Start new session, tell Claude to read the `.md` and continue

---

## 8. Best Practices Summary

### For Long-Running Tasks

1. **Use Plan Mode First** - Shift+Tab twice before execution
2. **Structure Tasks Clearly** - Break into explicit todo items
3. **Leverage Subagents** - Keep main context clean
4. **Use Background Agents** - Fire off tasks, continue working
5. **Self-Review** - Have Claude review its own changes (~50% bug reduction)
6. **Run Multiple Instances** - Use git worktrees for parallel development

### CLAUDE.md Guidelines

- Keep under 300 lines (ideally under 100)
- Start with `/init` and iterate
- Include: tech stack, commands, code style, testing, gotchas
- Use `@path/to/file` to reference documentation
- Commit to version control for team consistency

### Workflow from Boris Cherny (Creator)

1. Start in Plan mode (Shift+Tab twice)
2. Go back and forth until plan is solid
3. Switch to auto-accept edits mode
4. Claude can usually "1-shot it" from a good plan

---

## 9. Source References

### Official Anthropic

| Resource | URL |
|----------|-----|
| Session Bridging | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| Best Practices | https://www.anthropic.com/engineering/claude-code-best-practices |
| Autonomous Mode | https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously |
| Agent SDK | https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk |

### Claude Code Documentation

| Resource | URL |
|----------|-----|
| Memory Management | https://code.claude.com/docs/en/memory |
| Subagents | https://code.claude.com/docs/en/sub-agents |
| GitHub Actions | https://code.claude.com/docs/en/github-actions |
| Headless Mode | https://code.claude.com/docs/en/headless |
| CLI Reference | https://code.claude.com/docs/en/cli-reference |

### Community Tools

| Tool | URL |
|------|-----|
| Claude-Flow | https://github.com/ruvnet/claude-flow |
| Cline | https://github.com/cline/cline |
| Aider | https://github.com/Aider-AI/aider |
| Continue.dev | https://github.com/continuedev/continue |
| Awesome Claude Code | https://github.com/hesreallyhim/awesome-claude-code |
| Claude Code Tips | https://github.com/ykdojo/claude-code-tips |

### Developer Blogs

| Author | URL |
|--------|-----|
| Boris Cherny Workflow | https://dev.to/sivarampg/how-the-creator-of-claude-code-uses-claude-code-a-complete-breakdown-4f07 |
| Running Claude in Loop | https://anandchowdhary.com/blog/2025/running-claude-code-in-a-loop |
| CLAUDE.md Guide | https://www.builder.io/blog/claude-md-guide |
| Session Management | https://stevekinney.com/courses/ai-development/claude-code-session-management |