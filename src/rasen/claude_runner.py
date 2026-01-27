"""Claude Code CLI wrapper for agent sessions."""

from __future__ import annotations

import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any

from rasen.exceptions import ConfigurationError, SessionError

logger = logging.getLogger(__name__)

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
    prompt: str,
    project_dir: Path,
    timeout_seconds: int = 1800,  # 30 minutes default
    debug_log_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a Claude Code CLI session in non-interactive mode.

    Uses --print flag to run Claude Code in non-interactive mode, processing
    the prompt and exiting without requiring user interaction.

    Args:
        prompt: Prompt content to send to Claude
        project_dir: Working directory for the session
        timeout_seconds: Session timeout in seconds
        debug_log_dir: Optional directory for detailed debug logs

    Returns:
        CompletedProcess with returncode, stdout, stderr
        The process object also has a `session_id` attribute added for tracking

    Raises:
        SessionError: If Claude Code CLI fails or times out
    """
    # Generate unique session ID for tracking
    session_id = str(uuid.uuid4())

    # Build command with session ID and optional debug logging
    cmd = [
        "claude",
        "chat",
        "--print",
        "--permission-mode",
        "bypassPermissions",
        "--session-id",
        session_id,
    ]

    # Add debug logging if requested
    if debug_log_dir:
        debug_log_dir.mkdir(parents=True, exist_ok=True)
        debug_log_file = debug_log_dir / f"claude_session_{session_id[:8]}.log"
        cmd.extend(["--debug-file", str(debug_log_file)])
        logger.info(f"Session {session_id[:8]}: Debug logs → {debug_log_file}")

    logger.info(
        f"Session {session_id[:8]}: Starting Claude session "
        f"(timeout={timeout_seconds}s, cwd={project_dir})"
    )

    try:
        # Run claude chat with --print flag for non-interactive execution
        # Pipe prompt content via stdin
        result = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,  # CRITICAL: Capture stdout/stderr for event parsing
            cwd=project_dir,
            timeout=timeout_seconds,
            check=False,  # Don't raise on non-zero exit
        )

        # Attach session ID to result for tracking
        result.session_id = session_id  # type: ignore[attr-defined]

        # Log session completion
        status = "success" if result.returncode == 0 else "failed"
        logger.info(
            f"Session {session_id[:8]}: Completed with {status} "
            f"(returncode={result.returncode}, "
            f"stdout={len(result.stdout)} chars, "
            f"stderr={len(result.stderr)} chars)"
        )

        # Log stderr if present (usually contains warnings/errors)
        if result.stderr:
            logger.warning(f"Session {session_id[:8]}: stderr output:\n{result.stderr[:1000]}")

        return result

    except subprocess.TimeoutExpired as e:
        logger.error(f"Session {session_id[:8]}: Timed out after {timeout_seconds}s")
        raise SessionError(
            f"Session {session_id[:8]} timed out after {timeout_seconds}s"
        ) from e
    except FileNotFoundError as e:
        logger.error("Claude Code CLI not found")
        raise SessionError(
            "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        ) from e
    except Exception as e:
        logger.error(f"Session {session_id[:8]}: Failed with error: {e}")
        raise SessionError(f"Session {session_id[:8]} failed: {e}") from e


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
