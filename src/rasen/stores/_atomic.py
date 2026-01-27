"""Atomic file operations for safe state persistence."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

# Platform-specific locking
if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def file_lock(path: Path, shared: bool = False) -> Iterator[None]:
        """Windows file locking using msvcrt.

        Args:
            path: Path to file to lock
            shared: If True, allow shared read access

        Yields:
            None - context manager
        """
        # Ensure file exists
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        with path.open("r+b") as f:
            try:
                if shared:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBRLCK, 1)
                else:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                yield
            finally:
                with suppress(OSError):
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    @contextmanager
    def file_lock(path: Path, shared: bool = False) -> Iterator[None]:
        """Unix file locking using fcntl.

        Args:
            path: Path to file to lock
            shared: If True, allow shared read access

        Yields:
            None - context manager
        """
        # Ensure file exists
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        with path.open("r+b") as f:
            try:
                if shared:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                else:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def atomic_write(path: Path, content: str) -> None:
    """Write content atomically using temp file + rename.

    This ensures that readers never see partial writes.

    Args:
        path: Target file path.
        content: Content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        temp_path.write_text(content)
        temp_path.replace(path)  # Atomic on POSIX, close-enough on Windows
    except Exception:
        # Clean up temp file on failure
        temp_path.unlink(missing_ok=True)
        raise
