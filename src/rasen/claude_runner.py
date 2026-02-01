"""Claude Code CLI wrapper for agent sessions."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rasen.exceptions import ConfigurationError, SessionError


def _load_anthropic_env() -> dict[str, str]:
    """Load Anthropic auth env vars from shell config files.

    Reads ANTHROPIC_* vars from ~/.zshrc, ~/.bashrc, ~/.profile
    to make them available for Claude Code subprocess.

    Returns:
        Dict of environment variables to add
    """
    env_vars: dict[str, str] = {}

    # Files to check for env vars
    config_files = [
        Path.home() / ".zshrc",
        Path.home() / ".bashrc",
        Path.home() / ".profile",
        Path.home() / ".bash_profile",
    ]

    # Pattern to match export statements
    export_pattern = re.compile(
        r'^export\s+(ANTHROPIC_\w+)=["\']?([^"\'#\n]+)["\']?',
        re.MULTILINE
    )

    for config_file in config_files:
        if config_file.exists():
            try:
                content = config_file.read_text()
                for match in export_pattern.finditer(content):
                    var_name = match.group(1)
                    var_value = match.group(2).strip()
                    if var_name not in env_vars:  # First found wins
                        env_vars[var_name] = var_value
                        logger.debug(f"Loaded {var_name} from {config_file}")
            except Exception as e:
                logger.warning(f"Could not read {config_file}: {e}")

    return env_vars

logger = logging.getLogger(__name__)


@dataclass
class SessionRunResult:
    """Result from a Claude session with metrics."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    session_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


def _stream_output(pipe: Any, prefix: str, output_lines: list[str], log_file: Path | None) -> None:
    """Stream output from a pipe to logger and collect lines.

    Args:
        pipe: subprocess pipe to read from
        prefix: prefix for log messages (e.g., "STDOUT" or "STDERR")
        output_lines: list to collect output lines
        log_file: optional file to write raw output
    """
    try:
        for line in iter(pipe.readline, ""):
            if line:
                line_stripped = line.rstrip()
                output_lines.append(line)
                # Log to orchestration log for visibility
                logger.debug(f"[{prefix}] {line_stripped[:200]}")
                # Also write to log file if provided
                if log_file:
                    with log_file.open("a") as f:
                        f.write(f"[{prefix}] {line}")
    except Exception as e:
        logger.warning(f"Error streaming {prefix}: {e}")


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
    model: str | None = None,
) -> SessionRunResult:
    """Run a Claude Code CLI session in non-interactive mode.

    Uses --print flag with --output-format stream-json to run Claude Code
    in non-interactive mode, processing the prompt and extracting token usage.

    Args:
        prompt: Prompt content to send to Claude
        project_dir: Working directory for the session
        timeout_seconds: Session timeout in seconds
        debug_log_dir: Optional directory for detailed debug logs

    Returns:
        SessionRunResult with returncode, stdout, stderr, and token metrics

    Raises:
        SessionError: If Claude Code CLI fails or times out
    """
    # Generate unique session ID for tracking
    session_id = str(uuid.uuid4())

    # Build command with session ID, stream-json output, and optional debug logging
    cmd = [
        "claude",
        "chat",
        "--print",
        "--verbose",  # Required for stream-json with --print
        "--output-format",
        "stream-json",  # Get token usage from streaming JSON
        "--permission-mode",
        "bypassPermissions",
        "--session-id",
        session_id,
    ]

    # Add model if specified
    if model:
        cmd.extend(["--model", model])
        logger.info(f"Session {session_id[:8]}: Using model {model}")

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
    logger.info(f"Session {session_id[:8]}: Waiting for Claude response (this may take a while)...")

    # Prepare streaming log file
    stream_log_file = None
    if debug_log_dir:
        stream_log_file = debug_log_dir / f"claude_stream_{session_id[:8]}.log"

    try:
        # Build environment with Anthropic auth vars from shell config
        env = os.environ.copy()
        anthropic_env = _load_anthropic_env()
        env.update(anthropic_env)
        if anthropic_env:
            logger.info(f"Loaded Anthropic env vars: {list(anthropic_env.keys())}")

        # Use Popen for streaming output instead of blocking run()
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_dir,
            env=env,
        )

        # Send prompt via stdin
        if process.stdin:
            process.stdin.write(prompt)
            process.stdin.close()

        # Collect output while streaming
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        # Stream stdout and stderr in separate threads
        stdout_thread = threading.Thread(
            target=_stream_output,
            args=(process.stdout, "OUT", stdout_lines, stream_log_file),
        )
        stderr_thread = threading.Thread(
            target=_stream_output,
            args=(process.stderr, "ERR", stderr_lines, stream_log_file),
        )

        stdout_thread.start()
        stderr_thread.start()

        # Log periodic status while waiting
        logger.info(f"Session {session_id[:8]}: Claude is working...")

        # Wait for process with timeout
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as e:
            process.kill()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            logger.error(f"Session {session_id[:8]}: Timed out after {timeout_seconds}s")
            msg = f"Session {session_id[:8]} timed out after {timeout_seconds}s"
            raise SessionError(msg) from e

        # Wait for output threads to finish
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        # Parse streaming JSON to extract token usage and text content
        total_input_tokens = 0
        total_output_tokens = 0
        text_content: list[str] = []

        for line in stdout_lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            try:
                data = json.loads(line_stripped)
                # Extract token usage from assistant messages
                if data.get("type") == "assistant" and "message" in data:
                    msg = data["message"]
                    if "usage" in msg:
                        usage = msg["usage"]
                        # Include cache tokens in total input count
                        input_base = usage.get("input_tokens", 0)
                        cache_creation = usage.get("cache_creation_input_tokens", 0)
                        cache_read = usage.get("cache_read_input_tokens", 0)
                        total_input_tokens = input_base + cache_creation + cache_read
                        total_output_tokens = usage.get("output_tokens", total_output_tokens)
                # Extract text content from result messages
                if data.get("type") == "result" and "result" in data:
                    text_content.append(data["result"])
                # Also handle content blocks for text
                if "content" in data:
                    content = data["content"]
                    if isinstance(content, str):
                        text_content.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_content.append(block.get("text", ""))
            except json.JSONDecodeError:
                # Not JSON, treat as raw text content
                text_content.append(line)

        # Build result object with token metrics
        stdout_str = "".join(text_content) if text_content else "".join(stdout_lines)
        stderr_str = "".join(stderr_lines)

        result = SessionRunResult(
            args=cmd,
            returncode=returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            session_id=session_id,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_input_tokens + total_output_tokens,
        )

        # Log session completion with token usage
        status = "success" if result.returncode == 0 else "failed"
        logger.info(
            f"Session {session_id[:8]}: Completed with {status} "
            f"(returncode={result.returncode}, "
            f"tokens={result.total_tokens} (in={result.input_tokens}, out={result.output_tokens}), "
            f"stdout={len(result.stdout)} chars)"
        )

        # Log stderr if present (usually contains warnings/errors)
        if result.stderr:
            logger.warning(f"Session {session_id[:8]}: stderr output:\n{result.stderr[:1000]}")

        return result

    except SessionError:
        raise
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
