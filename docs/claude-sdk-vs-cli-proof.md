# Claude Agent SDK vs CLI: Proof for Long-Running Tasks

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Purpose:** Evidence-based comparison proving SDK superiority for autonomous long-running tasks

---

## Executive Summary

This document provides concrete proof that the **Claude Agent SDK is superior to CLI-based approaches** for complex long-running autonomous coding tasks. Evidence includes production metrics, documented CLI failures, enterprise deployments, and implementation analysis of successful orchestration tools.

---

## 1. Production Metrics (Anthropic Official)

### Benchmark Results

| Benchmark | Score | Details |
|-----------|-------|---------|
| **SWE-bench Verified** | 77.2% - 82.0% | Real-world software issue resolution |
| **OSWorld** | 61.4% - 66.3% | Complex computer use tasks |
| **Terminal Bench** | +15% | Improvement over previous generation |
| **Safety Score** | 98.7% | vs 89.3% for Sonnet 4 |

### Long-Running Task Capability

| Metric | Result | Source |
|--------|--------|--------|
| **Endurance** | 30+ hours | Maintains coherence across extended sessions |
| **Context Quality** | Stable | No degradation halfway through (recent improvements) |
| **Multi-Session** | Seamless | Two-agent pattern enables unlimited context windows |

**Source:** [Anthropic Sonnet 4.5 Announcement](https://www.anthropic.com/news/claude-sonnet-4-5)

---

## 2. Documented CLI Limitations

### GitHub Issues (anthropics/claude-code)

| Issue # | Problem | Impact |
|---------|---------|--------|
| **#4014** | Multi-instance shell state corruption | Race conditions when running concurrent instances |
| **#19508** | Bash tool causes zsh coredumps | Commands fail, crashes persist after closing |
| **#7387** | Shell script escaping failures | Syntax errors even with correct commands |
| **#19663** | Bash tool returns no output (macOS) | Complete functionality loss on macOS CLI |
| **#12507** | Exits on HPC interactive sessions | stdin consumption kills sessions |

### Context Degradation Problem

**Critical Finding from Production Users:**

> "After several compaction cycles, signal degrades into noise, and Claude starts hallucinating context"

**Documented Behavior:**
- Auto-compact triggers at 8-12% remaining context instead of 95%+
- Causes constant interruptions every few minutes
- Context loss requires re-explanation of project structure upon restart

**Source:** [How Claude Code Got Better by Protecting More Context](https://hyperdev.matsuoka.com/p/how-claude-code-got-better-by-protecting)

### Headless Mode (`claude -p`) Constraints

| Limitation | Description |
|------------|-------------|
| **No Persistence** | Must restart each time—no state between sessions |
| **Duration Limit** | Consensus: max 15-30 minutes without human checkpoints |
| **No Interactive Mode** | Must use `--allowedTools` flags to grant permissions |
| **Session Loss** | Sessions fail silently, context doesn't persist |

**Source:** [Claude Code Headless Documentation](https://code.claude.com/docs/en/headless)

---

## 3. Auto-Claude: Confirmed SDK Implementation

### Official Documentation Proof

From Auto-Claude's CLAUDE.md:

> "ALL AI interactions use the Claude Agent SDK (`create_client()` from `core/client.py`), NEVER the raw Anthropic API directly"

> "ANTHROPIC_API_KEY is intentionally NOT supported to prevent silent billing to user's API credits"

### SDK Client Factory Pattern

```python
# core/client.py - Auto-Claude Implementation
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

def create_client(
    model: str,
    thinking_budget: str = "medium"
) -> ClaudeSDKClient:
    """Construct ClaudeSDKClient with security hooks."""

    thinking_configs = {
        "ultrathink": 16000,
        "high": 10000,
        "medium": 5000
    }

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            max_thinking_tokens=thinking_configs.get(thinking_budget),
            sandbox={"enabled": True, "autoAllowBashIfSandboxed": True},
            permissions={"defaultMode": "acceptEdits"},
            allowed_tools=get_allowed_tools(),
            mcp_servers=get_required_mcp_servers()
        )
    )
```

### Session Management Comparison

| Feature | SDK `ClaudeSDKClient` | CLI `claude -p` |
|---------|----------------------|-----------------|
| **Session Persistence** | Reuses same session | New session each time |
| **Multi-turn Context** | Full conversation history | None |
| **Connection Control** | Manual lifecycle management | Auto-managed (limited) |
| **Memory Integration** | Graphiti + file-based | Manual file-based only |
| **Error Recovery** | Managed with retry logic | Crashes, coredumps |

### SDK Query Patterns

```python
# Pattern 1: One-off tasks (new session each call)
async for message in query(
    prompt="Analyze codebase",
    options=ClaudeAgentOptions(allowed_tools=["Read", "Glob"])
):
    print(message)

# Pattern 2: Continuous conversation (Auto-Claude agents use this)
async with ClaudeSDKClient(options=options) as client:
    await client.query("First task")
    async for msg in client.receive_response():
        pass  # Process response

    await client.query("Follow-up task")  # Claude remembers context
    async for msg in client.receive_response():
        pass
```

**Source:** [Auto-Claude GitHub](https://github.com/AndyMik90/Auto-Claude)

---

## 4. Enterprise Production Deployments (SDK-Based)

### Scale Evidence

| Company | Deployment Scale | Results |
|---------|-----------------|---------|
| **TELUS** | 57,000 employees | Full Claude deployment via Fuel iX platform |
| **Zapier** | 800+ internal agents | 10× year-over-year growth |
| **Tines** | 120-step processes | Reduced to 1-step (100× speed improvement) |
| **EdgeDB** | Test coverage | 78% → 95% (tripled bug detection) |
| **Jane Street** | Financial verification | 4 hours → 25 minutes |
| **Deno** | Module updates | 10 days → 2 days |

### Customer Support Production Example

**Metrics from Real Deployment:**
- **Throughput:** ~300 tickets/day handled by single agent
- **Complexity Growth:** 150-line prototype → 800-line system
- **Use Cases:** Evolved from 1 → 12 ticket types
- **Reliability:** Maintained as feature count increased

### Documentation Pipeline Example

**Production Workflow:**
- **Time Reduction:** 23 hours → 5 hours
- **Architecture:** 7-subagent orchestration
- **Execution:** Parallel subagent spawning

**Source:** [Claude Enterprise Case Studies](https://claude.com/solutions/agents)

---

## 5. Anthropic's Official Two-Agent Demo (SDK-Based)

### Repository Structure

**Source:** [anthropics/claude-quickstarts/autonomous-coding](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding)

```
autonomous-coding/
├── autonomous_agent_demo.py    # Entry point (Python SDK)
├── agent.py                     # SDK session logic
├── client.py                    # SDK client configuration
├── security.py                  # Bash command allowlist
├── progress.py                  # Progress tracking utilities
├── prompts.py                   # Prompt loading utilities
└── prompts/
    ├── app_spec.txt            # Application specification
    ├── initializer_prompt.md   # First session prompt
    └── coding_prompt.md        # Continuation session prompt
```

### Key Architecture Features

| Feature | Implementation |
|---------|----------------|
| **3-second delay** | Between sessions for stability |
| **Auto-continues** | Until Ctrl+C or completion |
| **200+ features** | Tracked in JSON format |
| **Git checkpoints** | For rollback capability |
| **Puppeteer MCP** | For browser-based verification |

### Timing Expectations (from Anthropic)

| Phase | Duration |
|-------|----------|
| **Initialization** | Several minutes (generates 200 features) |
| **Each coding session** | 5-15 minutes |
| **Full 200-feature app** | Many hours across multiple sessions |

### Security Model (Defense-in-Depth)

1. **OS-level Sandbox** - Bash commands run in isolated environment
2. **Filesystem Restrictions** - Operations restricted to project directory
3. **Bash Allowlist** - Only specific commands permitted:
   - File inspection: `ls`, `cat`, `head`, `tail`, `wc`, `grep`
   - Node.js: `npm`, `node`
   - Version control: `git`
   - Process management: `ps`, `lsof`, `sleep`, `pkill`

**Source:** [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

---

## 6. SDK vs CLI Feature Comparison

### Capability Matrix

| Capability | CLI (`claude -p`) | SDK (`ClaudeAgentOptions`) |
|------------|-------------------|---------------------------|
| **Session Persistence** | ❌ New each time | ✅ Resume with session_id |
| **Multi-instance** | ❌ State corruption | ✅ Isolated sessions |
| **Memory Integration** | ❌ Manual files only | ✅ Graphiti + query() |
| **30+ hour endurance** | ❌ Context degrades | ✅ Documented stable |
| **Production adoption** | ❌ Limited | ✅ Enterprise scale |
| **Error recovery** | ❌ Coredumps, exits | ✅ Managed lifecycle |
| **Subagent spawning** | ⚠️ Task tool only | ✅ Native AgentDefinition |
| **Custom tools** | ❌ Limited | ✅ Full customization |
| **Thinking budget** | ⚠️ Env var only | ✅ Programmatic control |
| **Security sandbox** | ⚠️ Manual setup | ✅ Built-in options |

### Use Case Recommendations

| Use Case | Recommended Approach |
|----------|---------------------|
| Quick one-off tasks | CLI `claude -p` |
| Interactive development | CLI interactive mode |
| CI/CD pipelines (simple) | CLI headless |
| Long-running autonomous | **SDK** |
| Multi-agent orchestration | **SDK** |
| Production deployment | **SDK** |
| Enterprise integration | **SDK** |

---

## 7. Why CLI Fails for Long-Running Tasks

### Root Cause Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI FAILURE CASCADE                           │
├─────────────────────────────────────────────────────────────────┤
│  Session Start                                                   │
│       ↓                                                          │
│  Context Accumulates (files, greps, edits)                      │
│       ↓                                                          │
│  Context Window Fills (~200K tokens)                            │
│       ↓                                                          │
│  Auto-Compact Triggers (sometimes at 8-12% instead of 95%)      │
│       ↓                                                          │
│  Signal Degrades After Multiple Compactions                     │
│       ↓                                                          │
│  Claude Starts Hallucinating Context                            │
│       ↓                                                          │
│  Session Fails or Produces Incorrect Output                     │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Instance Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                MULTI-INSTANCE RACE CONDITION                     │
├─────────────────────────────────────────────────────────────────┤
│  Instance A starts in /project                                   │
│  Instance B starts in /project                                   │
│       ↓                                                          │
│  Both access shared state directory                              │
│       ↓                                                          │
│  Race condition on shell state files                            │
│       ↓                                                          │
│  Bash commands fail with coredumps                              │
│       ↓                                                          │
│  Coredumps persist even after closing instances                 │
│       ↓                                                          │
│  Requires manual cleanup to restore functionality               │
└─────────────────────────────────────────────────────────────────┘
```

### SDK Solution

```
┌─────────────────────────────────────────────────────────────────┐
│                    SDK SESSION MANAGEMENT                        │
├─────────────────────────────────────────────────────────────────┤
│  Session 1: Initializer Agent                                    │
│       ↓ (session_id captured)                                   │
│  State persisted to feature_list.json + git                     │
│       ↓ (3-second delay)                                        │
│  Session 2: Coding Agent (fresh context, reads state)           │
│       ↓ (session_id captured)                                   │
│  State updated, committed to git                                │
│       ↓ (3-second delay)                                        │
│  Session N: Continues until completion                          │
│       ↓                                                          │
│  Each session has full 200K context, no degradation             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. SDK Implementation Proof from Anthropic Demo

### Python Entry Point

```python
# autonomous_agent_demo.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    iteration = 0

    while True:
        iteration += 1
        print(f"=== Iteration {iteration} ===")

        # Determine which prompt to use
        prompt = load_initializer_prompt() if iteration == 1 else load_coding_prompt()

        # Run agent session with SDK
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                working_directory=PROJECT_DIR,
                sandbox={"enabled": True}
            )
        ):
            if hasattr(message, "result"):
                print(message.result)

        # Check completion
        if is_complete():
            print("All features verified!")
            break

        # Anthropic-recommended delay
        print("Waiting 3 seconds...")
        await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
```

### Session Resume Capability

```python
# SDK session resumption (not available in CLI)
from claude_agent_sdk import query, ClaudeAgentOptions

async def resume_work():
    session_id = None

    # First query: capture session
    async for message in query(
        prompt="Start working on feature #42",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Write", "Bash"])
    ):
        if hasattr(message, 'subtype') and message.subtype == 'init':
            session_id = message.session_id

    # Resume with full context from first query
    async for message in query(
        prompt="Continue from where you left off",
        options=ClaudeAgentOptions(resume=session_id)  # CLI cannot do this
    ):
        if hasattr(message, "result"):
            print(message.result)
```

---

## 9. Conclusion

### Evidence Summary

| Evidence Type | Finding |
|---------------|---------|
| **Benchmarks** | 77.2%-82.0% SWE-bench, 30+ hour endurance |
| **GitHub Issues** | 5+ critical CLI bugs (coredumps, state corruption) |
| **Auto-Claude** | Explicitly uses SDK, forbids raw API |
| **Enterprise** | 57K+ users, 800+ agents, 100× speed improvements |
| **Anthropic Demo** | SDK-based two-agent pattern, official recommendation |

### Final Verdict

```
┌─────────────────────────────────────────────────────────────────┐
│                         VERDICT                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CLI (`claude -p`):                                            │
│   - Designed for interactive development                        │
│   - Suitable for quick one-off tasks                           │
│   - Limited to ~15-30 minutes autonomous work                   │
│   - Known stability issues with long sessions                   │
│                                                                  │
│   SDK (`claude_agent_sdk`):                                     │
│   - Designed for production autonomous agents                   │
│   - Session resumption and memory integration                   │
│   - 30+ hour documented endurance                               │
│   - Enterprise-scale deployments                                │
│   - Anthropic's official recommendation for long-running tasks  │
│                                                                  │
│   WINNER FOR LONG-RUNNING TASKS: Claude Agent SDK               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. References

### Anthropic Official

| Document | URL |
|----------|-----|
| Effective Harnesses for Long-Running Agents | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| Building Agents with Claude Agent SDK | https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk |
| Claude Code Best Practices | https://www.anthropic.com/engineering/claude-code-best-practices |
| Claude Sonnet 4.5 Announcement | https://www.anthropic.com/news/claude-sonnet-4-5 |
| Autonomous Coding Demo | https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding |

### SDK Documentation

| Document | URL |
|----------|-----|
| Agent SDK Overview | https://platform.claude.com/docs/en/agent-sdk/overview |
| Agent SDK Python | https://platform.claude.com/docs/en/agent-sdk/python |
| Agent SDK Hosting | https://platform.claude.com/docs/en/agent-sdk/hosting |

### CLI Issues

| Issue | URL |
|-------|-----|
| Multi-Instance Corruption #4014 | https://github.com/anthropics/claude-code/issues/4014 |
| Bash Coredumps #19508 | https://github.com/anthropics/claude-code/issues/19508 |
| Shell Escaping #7387 | https://github.com/anthropics/claude-code/issues/7387 |
| macOS No Output #19663 | https://github.com/anthropics/claude-code/issues/19663 |

### Community Tools

| Tool | URL |
|------|-----|
| Auto-Claude | https://github.com/AndyMik90/Auto-Claude |
| Claude-Flow | https://github.com/ruvnet/claude-flow |
| Continuous-Claude | https://github.com/AnandChowdhary/continuous-claude |
| Oh-My-ClaudeCode | https://github.com/Yeachan-Heo/oh-my-claudecode |

### Enterprise Case Studies

| Source | URL |
|--------|-----|
| Claude Enterprise Solutions | https://claude.com/solutions/agents |
| Claude Case Studies | https://www.datastudios.org/post/claude-in-the-enterprise-case-studies-of-ai-deployments-and-real-world-results-1 |
