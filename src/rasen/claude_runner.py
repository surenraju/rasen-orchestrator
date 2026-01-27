"""Claude Code CLI wrapper for agent sessions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rasen.exceptions import ConfigurationError, SessionError

# Agent type configurations
AGENT_CONFIGS: dict[str, dict[str, Any]] = {
    "initializer": {
        "prompt_template": "prompts/initializer.md",
        "read_only": False,
    },
    "coder": {
        "prompt_template": "prompts/coder.md",
        "read_only": False,
    },
    "reviewer": {
        "prompt_template": "prompts/reviewer.md",
        "read_only": True,  # Reviewer cannot modify files
    },
    "qa": {
        "prompt_template": "prompts/qa.md",
        "read_only": True,  # QA cannot modify files
    },
}


def run_claude_session(
    prompt_file: Path,
    project_dir: Path,
    timeout_seconds: int = 1800,  # 30 minutes default
) -> subprocess.CompletedProcess[bytes]:
    """Run a Claude Code CLI session.

    Args:
        prompt_file: Path to prompt markdown file
        project_dir: Working directory for the session
        timeout_seconds: Session timeout in seconds

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        SessionError: If Claude Code CLI fails or times out
    """
    try:
        result = subprocess.run(
            ["claude", "chat", "--file", str(prompt_file)],
            cwd=project_dir,
            timeout=timeout_seconds,
            capture_output=False,  # Show output to user in real-time
            check=False,  # Don't raise on non-zero exit
        )
        return result
    except subprocess.TimeoutExpired as e:
        raise SessionError(f"Session timed out after {timeout_seconds}s") from e
    except FileNotFoundError as e:
        raise SessionError(
            "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        ) from e
    except Exception as e:
        raise SessionError(f"Failed to run Claude Code session: {e}") from e


def get_agent_config(agent_type: str) -> dict[str, Any]:
    """Get configuration for an agent type.

    Args:
        agent_type: Type of agent (initializer, coder, reviewer, qa)

    Returns:
        Agent configuration dictionary

    Raises:
        ConfigurationError: If agent type is invalid
    """
    if agent_type not in AGENT_CONFIGS:
        raise ConfigurationError(f"Invalid agent type: {agent_type}")
    return AGENT_CONFIGS[agent_type]
