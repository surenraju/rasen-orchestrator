"""Git operations for RASEN orchestrator."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rasen.exceptions import GitError


def get_current_commit(project_dir: Path) -> str:
    """Get current git commit hash.

    Args:
        project_dir: Path to git repository

    Returns:
        Full commit hash (SHA-1)

    Raises:
        GitError: If not a git repo or git command fails
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get current commit: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("Git not found. Please install git.") from e


def count_new_commits(project_dir: Path, since_commit: str) -> int:
    """Count commits made since a specific commit.

    Args:
        project_dir: Path to git repository
        since_commit: Commit hash to count from

    Returns:
        Number of new commits

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{since_commit}..HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to count commits: {e.stderr}") from e
    except ValueError as e:
        raise GitError(f"Invalid commit count returned: {e}") from e


def get_git_diff(project_dir: Path, since_commit: str) -> str:
    """Get git diff since a specific commit.

    Args:
        project_dir: Path to git repository
        since_commit: Commit hash to diff from

    Returns:
        Diff output as string

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "diff", since_commit, "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get diff: {e.stderr}") from e


def is_git_repo(project_dir: Path) -> bool:
    """Check if directory is a git repository.

    Args:
        project_dir: Path to check

    Returns:
        True if git repo, False otherwise
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_dir,
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def has_uncommitted_changes(project_dir: Path) -> bool:
    """Check if there are uncommitted changes.

    Args:
        project_dir: Path to git repository

    Returns:
        True if uncommitted changes exist

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check git status: {e.stderr}") from e


def get_last_commit_message(project_dir: Path) -> str:
    """Get the last commit message.

    Args:
        project_dir: Path to git repository

    Returns:
        Last commit message

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get commit message: {e.stderr}") from e
