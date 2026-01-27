# 螺旋 RASEN - Agent Orchestrator

```
╔═══════════════════════════════════════════════════════════╗
║   螺旋  RASEN                                             ║
║   Agent Orchestrator                                      ║
║                                                           ║
║   "The spiral that never stops turning"                   ║
╚═══════════════════════════════════════════════════════════╝
```

**RASEN** (螺旋 = Spiral in Japanese) is a production-ready orchestrator for long-running autonomous coding tasks using Claude Code CLI.

## Features

- **Multi-Agent Workflow**: Initializer → Coder → Reviewer → QA pipeline
- **Quality Gates**: Backpressure validation ensures tests pass before completion
- **Recovery**: Automatic stall detection and recovery from failures
- **Isolation**: Git worktree support for safe development
- **Background Mode**: Run multi-hour tasks unattended

## Installation

```bash
# Requires Python 3.12+
pip install -e .

# Or with uv
uv sync
```

## Quick Start

```bash
# Initialize a task
rasen init --task "Implement user authentication"

# Run orchestrator
rasen run

# Check status
rasen status
```

## Documentation

See `docs/plan.md` for the complete implementation plan and architecture.

## License

MIT
