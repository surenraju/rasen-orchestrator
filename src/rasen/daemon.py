"""Background daemon mode for long-running orchestration."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

from rasen.logging import get_logger

logger = get_logger(__name__)

# Global flag for graceful shutdown
_shutdown_requested = False


def request_shutdown() -> None:
    """Request graceful shutdown of daemon."""
    global _shutdown_requested  # noqa: PLW0603
    _shutdown_requested = True
    logger.info("Shutdown requested")


def should_shutdown() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_requested


def write_pid_file(pid_file: Path) -> None:
    """Write process ID to PID file.

    Args:
        pid_file: Path to PID file
    """
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    logger.info(f"PID {os.getpid()} written to {pid_file}")


def read_pid_file(pid_file: Path) -> int | None:
    """Read process ID from PID file.

    Args:
        pid_file: Path to PID file

    Returns:
        Process ID or None if file doesn't exist or is invalid
    """
    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        return pid if pid > 0 else None
    except (ValueError, OSError):
        return None


def remove_pid_file(pid_file: Path) -> None:
    """Remove PID file.

    Args:
        pid_file: Path to PID file
    """
    try:
        pid_file.unlink(missing_ok=True)
        logger.info(f"Removed PID file {pid_file}")
    except OSError as e:
        logger.warning(f"Failed to remove PID file: {e}")


def is_process_running(pid: int) -> bool:
    """Check if a process is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running
    """
    if pid <= 0:
        return False

    try:
        # Send signal 0 to check if process exists
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum: int, frame: object) -> None:  # noqa: ARG001
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name} ({signum})")
        request_shutdown()

    # Handle termination signals
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Handle SIGHUP for reload (treat as shutdown for now)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)


def daemonize(
    pid_file: Path,
    log_file: Path,
    working_dir: Path,
) -> None:
    """Daemonize the current process.

    This forks the process and runs it in the background.

    Args:
        pid_file: Path to PID file
        log_file: Path to log file for stdout/stderr
        working_dir: Working directory for daemon
    """
    # Check if daemon already running
    existing_pid = read_pid_file(pid_file)
    if existing_pid and is_process_running(existing_pid):
        raise RuntimeError(
            f"Daemon already running with PID {existing_pid}. Use 'rasen stop' to stop it first."
        )

    # Fork first time
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - wait a moment then exit
            time.sleep(0.5)
            sys.exit(0)
    except OSError as e:
        raise RuntimeError(f"Fork failed: {e}") from e

    # Decouple from parent environment
    os.chdir(str(working_dir))
    os.setsid()
    os.umask(0)

    # Fork second time to prevent zombie
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        raise RuntimeError(f"Second fork failed: {e}") from e

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    # Open log file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fd = os.open(str(log_file), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)

    # Redirect stdout and stderr to log file
    os.dup2(log_fd, sys.stdout.fileno())
    os.dup2(log_fd, sys.stderr.fileno())
    os.close(log_fd)

    # Close stdin
    with open(os.devnull) as devnull:  # noqa: PTH123
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    # Write PID file
    write_pid_file(pid_file)

    # Setup signal handlers
    setup_signal_handlers()

    logger.info(f"Daemon started with PID {os.getpid()}")


def stop_daemon(pid_file: Path, timeout: int = 30) -> bool:
    """Stop a running daemon.

    Args:
        pid_file: Path to PID file
        timeout: Seconds to wait for graceful shutdown

    Returns:
        True if daemon was stopped successfully
    """
    pid = read_pid_file(pid_file)
    if not pid:
        logger.info("No daemon running (no PID file)")
        return False

    if not is_process_running(pid):
        logger.info(f"Daemon with PID {pid} is not running")
        remove_pid_file(pid_file)
        return False

    logger.info(f"Stopping daemon with PID {pid}")

    # Send SIGTERM for graceful shutdown
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        logger.error(f"Failed to send SIGTERM to PID {pid}: {e}")
        return False

    # Wait for process to exit
    start = time.time()
    while time.time() - start < timeout:
        if not is_process_running(pid):
            logger.info("Daemon stopped successfully")
            remove_pid_file(pid_file)
            return True
        time.sleep(0.5)

    # Force kill if still running
    logger.warning("Daemon did not stop gracefully, sending SIGKILL")
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        if not is_process_running(pid):
            remove_pid_file(pid_file)
            return True
    except OSError as e:
        logger.error(f"Failed to kill daemon: {e}")

    return False


def get_daemon_status(pid_file: Path) -> dict[str, str | int | bool | None]:
    """Get status of daemon.

    Args:
        pid_file: Path to PID file

    Returns:
        Status dictionary with running, pid, etc.
    """
    pid = read_pid_file(pid_file)

    if not pid:
        return {"running": False, "pid": None}

    running = is_process_running(pid)

    return {
        "running": running,
        "pid": pid,
        "stale": not running,  # PID file exists but process not running
    }
