# Claude-Flow Framework - Architecture Analysis

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Source:** /claude-flow

---

## 1. Overview

**Claude-Flow** is a comprehensive multi-agent orchestration platform that enables AI swarm coordination with advanced features including consensus algorithms, neural learning, and high-performance vector search.

**Problem it Solves:**
- Orchestrates 60+ specialized AI agents in coordinated swarms
- Provides self-learning capabilities with pattern recognition
- Enables distributed consensus across multiple agents
- Offers high-performance semantic search (150x-12,500x faster than v2)
- Integrates seamlessly with Claude Code via MCP (Model Context Protocol)

**Key Statistics:**
- 60+ agent types organized by domain
- 26 CLI commands + 140+ subcommands
- 27 lifecycle hooks + 12 background workers
- 50+ MCP tools
- 49 Architecture Decision Records (ADRs)

---

## 2. Architecture Pattern

**Pattern Type:** Multi-Agent Swarm Orchestration with Pub/Sub + Consensus

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE-FLOW V3 ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  CLI/MCP    │ →  │  Swarm      │ →  │  Agents     │                  │
│  │  Interface  │    │  Coordinator│    │  (60+ types)│                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         ↓                  ↓                  ↓                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Hooks      │    │  Consensus  │    │  Memory     │                  │
│  │  (27 types) │    │  (Raft/BFT) │    │  (HNSW)     │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         ↓                  ↓                  ↓                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Workers    │    │  Message    │    │  Neural     │                  │
│  │  (12)       │    │  Bus        │    │  (SONA/RL)  │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Swarm Topologies

| Topology | Use Case | Coordination |
|----------|----------|--------------|
| **Hierarchical** | Single coordinator (Queen) | Top-down |
| **Mesh** | Peer-to-peer collaboration | Gossip protocol |
| **Hierarchical-Mesh** | Complex tasks (default) | Queen + peer coordination |
| **Adaptive** | Dynamic workloads | Auto-adjusting |

---

## 3. Core Components

### Package Structure (TypeScript Monorepo)

```
v3/
├── @claude-flow/cli/        # CLI application (26 commands)
├── @claude-flow/mcp/        # MCP server (50+ tools)
├── @claude-flow/swarm/      # Swarm coordination
├── @claude-flow/memory/     # Vector search (HNSW)
├── @claude-flow/neural/     # Self-learning (SONA, RL)
├── @claude-flow/hooks/      # Lifecycle hooks (27 types)
├── @claude-flow/security/   # AIDefence + validation
├── @claude-flow/aidefence/  # Threat detection
└── @claude-flow/shared/     # Common types and utilities
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `unified-coordinator.ts` | Main swarm orchestration (15-agent hierarchy) |
| `topology-manager.ts` | Network topology configuration |
| `message-bus.ts` | Inter-agent communication |
| `agent-pool.ts` | Agent lifecycle and pooling |
| `consensus/index.ts` | Consensus algorithm selection |
| `hnsw-index.ts` | Vector search with HNSW |
| `sona-manager.ts` | Self-Optimizing Neural Architecture |
| `hook-registry.ts` | Hook registration and priority |

---

## 4. Agent Implementation

### Does Claude-Flow Use SDK or CLI?

**Claude-Flow uses Claude Code's Task tool**, not direct SDK or CLI:

```javascript
// Spawn agents using Claude Code Task tool
Task({
  prompt: "You are the swarm coordinator...",
  subagent_type: "hierarchical-coordinator",
  description: "Coordinator phase",
  run_in_background: true
})
```

### 60+ Agent Types by Domain

**Core Development:**
- `coder` - Code generation
- `reviewer` - Code quality review
- `tester` - Test generation
- `planner` - Task planning
- `researcher` - Requirements analysis

**Swarm Coordination:**
- `hierarchical-coordinator` - Queen agent
- `mesh-coordinator` - Peer coordination
- `adaptive-coordinator` - Dynamic topology
- `collective-intelligence-coordinator` - Hive-mind

**Consensus & Distributed:**
- `byzantine-coordinator` - Byzantine Fault Tolerant
- `raft-manager` - Raft consensus
- `gossip-coordinator` - Gossip protocol
- `quorum-manager` - Quorum decisions

**SPARC Methodology:**
- `sparc-coord` - SPARC coordinator
- `specification` - Specification generation
- `pseudocode` - Pseudocode design
- `architecture` - Architecture design
- `refinement` - Code refinement

### 3-Tier Model Routing

| Tier | Model | Latency | Cost | Use Case |
|------|-------|---------|------|----------|
| 1 | Agent Booster (WASM) | <1ms | $0 | Simple transforms |
| 2 | Haiku | ~500ms | $0.0002 | Medium tasks |
| 3 | Sonnet/Opus | 2-5s | $0.003-0.015 | Complex reasoning |

---

## 5. Session Management

### Session Lifecycle

```typescript
interface IAgentSession {
  id: string;                // Unique session ID
  agentId: string;          // Associated agent
  terminalId: string;       // Workspace ID
  startTime: Date;          // Creation timestamp
  status: 'active' | 'paused' | 'terminated';
  lastActivity: Date;       // Last activity
  memoryBankId: string;     // Associated memory
}
```

### Session Operations

| Command | Purpose |
|---------|---------|
| `session start` | Initialize new session |
| `session get <id>` | Retrieve session |
| `session list` | List active sessions |
| `session restore` | Restore previous state |
| `session end` | Close and persist |
| `session cleanup` | Remove expired |

---

## 6. State Persistence

### Storage Locations

| Path | Format | Purpose |
|------|--------|---------|
| `./data/sessions.json` | JSON | Session array with metrics |
| `.claude/checkpoints/` | JSON | Full swarm state snapshots |
| `./data/memory/` | HNSW | Vector embeddings |
| `.claude-flow/` | Various | Runtime state |

### Checkpoint System

```json
{
  "swarmId": "swarm_1704067200000_abc123",
  "state": {
    "agents": [...],
    "tasks": [...],
    "metrics": {
      "tasksCompleted": 42,
      "averageLatency": 150
    }
  },
  "checkpoint": {
    "timestamp": "2026-01-27T10:25:00Z",
    "version": "3.0.0-alpha.184"
  }
}
```

---

## 7. Workflow Phases

### Standard Workflow Patterns

**Bug Fix (Code 1):**
```
1. Researcher → Analyze bug
2. Coder → Implement fix
3. Tester → Write tests
```
Topology: hierarchical, Consensus: raft, Agents: 3-4

**Feature Implementation (Code 3):**
```
1. Coordinator → Initialize swarm
2. Researcher → Analyze requirements
3. Architect → Design approach
4. Coder → Implement
5. Tester → Write tests
6. Reviewer → Quality check
```
Topology: hierarchical-mesh, Consensus: raft, Agents: 6

**Security Audit (Code 9):**
```
1. Coordinator → Plan scope
2. Security → Identify vulnerabilities
3. Architect → Design fixes
4. Coder → Implement patches
```
Topology: hierarchical, Consensus: byzantine, Agents: 4-5

### SPARC Methodology Phases

1. **Specification** - Define what to build
2. **Pseudocode** - Plan implementation
3. **Architecture** - Design structure
4. **Refinement** - Polish and optimize
5. **Completion** - Testing and validation

---

## 8. Subagent Spawning

### Spawning via Task Tool

```javascript
// Parallel agent spawning (Claude Code Task tool)
Task({
  prompt: "Analyze requirements",
  subagent_type: "researcher",
  run_in_background: true
})

Task({
  prompt: "Design architecture",
  subagent_type: "architect",
  run_in_background: true
})
```

### Agent Pool Management

```typescript
interface AgentPoolConfig {
  minAgents: number;         // 1
  maxAgents: number;         // 15
  idleTimeoutMs: number;     // 300,000 (5 min)
}
```

### Agent States

```
spawning → initializing → idle → busy → paused → terminating → offline
```

---

## 9. Configuration

### Configuration File

```json
{
  "version": "3.0.0-alpha.184",
  "swarm": {
    "topology": "hierarchical-mesh",
    "maxAgents": 15,
    "consensus": {
      "algorithm": "raft",
      "threshold": 0.66
    }
  },
  "memory": {
    "backend": "hybrid",
    "hnsw": {
      "enabled": true,
      "dimensions": 1536,
      "M": 16
    }
  },
  "neural": {
    "enabled": true,
    "learningAlgorithms": ["ppo", "a2c", "dqn"]
  },
  "hooks": {
    "enabled": true,
    "workers": { "count": 12 }
  }
}
```

### 27 Lifecycle Hooks

| Hook Type | Trigger |
|-----------|---------|
| `PreToolUse` | Before tool execution |
| `PostToolUse` | After tool execution |
| `SessionStart` | Session initialization |
| `SessionEnd` | Session termination |
| `UserPromptSubmit` | User input received |
| `Stop` | Agent stop signal |
| `PreCompact` | Before context compaction |

---

## 10. Key Files

### Entry Points

| File | Purpose |
|------|---------|
| `v3/@claude-flow/cli/bin/cli.js` | Main CLI executable |
| `v3/@claude-flow/mcp/src/index.ts` | MCP server entry |

### Core Coordination

| File | Purpose |
|------|---------|
| `swarm/src/unified-coordinator.ts` | Main swarm orchestration |
| `swarm/src/topology-manager.ts` | Topology configuration |
| `swarm/src/message-bus.ts` | Inter-agent communication |
| `swarm/src/consensus/index.ts` | Consensus selection |

### Memory and Learning

| File | Purpose |
|------|---------|
| `memory/src/hnsw-index.ts` | Vector search |
| `neural/src/sona-manager.ts` | Self-Optimizing Neural Architecture |
| `neural/src/reinforcement-learning.ts` | 9 RL algorithms |

---

## 11. Performance Characteristics

### V3 Performance Targets (Achieved)

| Metric | Target | Status |
|--------|--------|--------|
| Agent Coordination (15 agents) | <100ms | ✅ |
| Consensus Latency | <100ms | ✅ |
| Message Throughput | 1000+ msgs/sec | ✅ |
| MCP Startup | <400ms | ✅ |
| HNSW Search | 150x-12,500x faster | ✅ |
| Memory Reduction | 50-75% | ✅ |

### Scalability

- Agent Count: 1-15 per swarm (higher with federation)
- Task Throughput: 100+ concurrent tasks
- Memory Capacity: 1M+ vectors with HNSW
- Pattern Storage: 10,000+ learned patterns

---

## Summary

**Claude-Flow** is a sophisticated **swarm orchestration platform** that:

| Aspect | Implementation |
|--------|----------------|
| **Agent Execution** | Claude Code Task tool (background spawning) |
| **Architecture** | Multi-agent swarm with consensus |
| **Session Management** | JSON-based with checkpoints |
| **State Persistence** | HNSW vectors + JSON state |
| **Parallel Execution** | 15 agents hierarchical-mesh |
| **Learning** | SONA + 9 RL algorithms |
| **Language** | TypeScript monorepo |

**Key Differentiator:** Self-learning swarm intelligence with Byzantine Fault Tolerant consensus, enabling reliable multi-agent coordination on complex software engineering tasks.
